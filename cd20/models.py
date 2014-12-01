import datetime
import importlib
import itertools
import logging
import math
import os
from os.path import join, exists
import cPickle as pickle
import random
import re
import shutil
import time

from django.db import models
from django.core.files.storage import Storage
from django.utils.timezone import now as utcnow
from django.utils.html import escape, mark_safe

import networkx as nx
import pcd.support.algorithms as algs
import pcd.cmty as cmty
from pcd.ioutil import read_any
algs.global_code_path.insert(0, '/srv/jako/cd-code/')

from .config import *
from . import utils
from . import cdas

logger = logging.getLogger(__name__)

# Create your models here.

def netfile_upload_to(instance, filename):
    path = join(instance.basedir, filename)
    return path

def new_ds_id():
    max_ = Dataset.objects.count() + 1   # "+ 1" handles count=0 simply
    idx = int(math.log10(max_*100))
    while True:
        id = random.randint(int(10**idx), int(10**(1+idx))-1)
        if Dataset.objects.filter(id=id):
            continue
        if os.path.exists(join(ROOTDIR, str(id))):
            continue
        return id

net_types = [
    ('auto', 'Auto (edgelist, GML, Pajek, gexf, graphml)'),
    ('adjlist', 'Adjacency list'),
    ('multiline_adjlist', 'Multiline Adjacency list'),
    ('edgelist', 'Edge list (weighted or unweighted)'),
    ('gexf', 'GEXF'),
    ('gml', 'GML'),
    ('graphml', 'GraphML'),
    ('jsonD3nl', 'JSON: d3.js node-link'),
    ('jsonD3a',  'JSON: d3.js adjecency'),
    ('jsonD3t', 'JSON: d3.js tree'),
    #('leda', 'LEDA'),             # not testable, don't have test input
    #('p2g', '(p2g)'),
    ('pajek', 'Pajek'),
    #('shp', 'GIS Shapefile'),     # requires OGR: http://www.gdal.org/
    #('yaml', 'YAML (networkx)'),  # requires PyYAML
    ]
# The field name above is used to find the reader: networkx.read_NAME.
# However, some openers do not follow this model.  The full paths to
# the readers of these things is below.  The modules are imported in
# the get_networkx method (so that we don't get ImportErrors here).
net_types_readers = dict(
    p2g='networkx.readwrite.p2g.read_p2g',
    json_node_link_data='networkx.readwrite.node_link_graph',
    jsonD3nl='cd20.utils.d3_node_link_graph',
    jsonD3a='cd20.utils.d3_adjacency_graph',
    jsonD3t='cd20.utils.d3_tree_graph',
)


class Dataset(models.Model):
    id = models.AutoField(primary_key=True, default=new_ds_id)
    generation = models.IntegerField(default=0)
    btime = models.DateTimeField("birth time", auto_now_add=True)
    mtime = models.DateTimeField("modification time", auto_now=True)
    atime = models.DateTimeField("access time", auto_now=True)
    netfile = models.FileField(upload_to=netfile_upload_to)
    nettype = models.CharField(max_length=10,
                               choices=net_types, default='auto')

    def __unicode__(self):
        if self.netfile:
            return u'<<Dataset(ds=%s, %s)>>'%(self.id, os.path.basename(self.netfile.name))
        return u'<<Dataset(ds=%s)>>'%(self.id, )
    def delete(self):
        self.clean_dir()
        super(Dataset, self).delete()
    def clean_dir(self):
        if self.netfile:
            self.del_network()
        if os.path.isdir(self.basedir):
            shutil.rmtree(self.basedir)
    def name(self):
        """Human-readable name for this dataset, for example for logging messages."""
        if self.netfile:
            return u"DS#%s (%s)"%(self.id, self.netfile_name())
        return u"DS#%s"%self.id
    def netfile_name(self):
        """Basename of uploaded network file (human-readable)"""
        if not self.netfile:
            return None
        return os.path.basename(self.netfile.name)

    @property
    def basedir(self):
        id = self.id
        if id is None:
            raise Exception("no ID")
        dir = join(ROOTDIR, str(id))
        if not exists(dir):
            os.mkdir(dir)
        return dir

    # This function should be abstracted out later
    def get_network_limits(self):
        """Get size limits of uploaded networks."""
        return dict(bytes=MAX_NETWORK_BYTES, nodes=MAX_NETWORK_NODES,
                    edges=MAX_NETWORK_EDGES)
    def set_network(self, f, messenger=None):
        """User has uploaded a graph, save and sanity check it"""
        from django.contrib import messages
        limits = self.get_network_limits()
        # Check size
        if f.size > limits['bytes']:
            netfile_upload_message = "Upload failed, network is too big"
            if messenger:
                messenger(messages.ERROR, netfile_upload_message)
            return netfile_upload_message
        # Do actual saving of network.
        self.clean_dir()
        self.netfile = f
        self.generation += 1
        self.save()
        # Make sure that network can be loaded
        try:
            g = self.get_networkx()
        except Exception as e:
            self.del_network()
            netfile_upload_message = 'Upload failed, network not openable (%s, %s)'%(self.nettype, e)
            if messenger:
                messenger(messages.ERROR, netfile_upload_message)
            return netfile_upload_message
        # Check nodes/edges limits...
        if len(g) > limits['nodes']:
            msg = 'Upload failed, too many nodes in network.'
            if messenger:
                messenger(messages.ERROR, msg)
            return msg
        if g.number_of_edges() > limits['edges']:
            self.del_network()
            msg = 'Upload failed, too many edges in network.'
            if messenger:
                messenger(messages.ERROR, msg)
            return msg
        # Run and save basic network statistics.
        self.study_network(g)
        netfile_upload_message = \
                 "Successfully uploaded %s: %s nodes, %s edges"%(
            f.name, int(self.prop_get('nodes')), int(self.prop_get('edges')))
        if messenger:
            messenger(messages.SUCCESS, netfile_upload_message)
        return netfile_upload_message

    def get_networkx(self):
        """Open graph and return networkx."""
        if not self.netfile:
            raise ValueError("No network has been given yet.")
        if self.nettype == 'auto':
            g = read_any(self.netfile.name)
        else:
            if self.nettype in net_types_readers:
                # Having the import logic explicitly contained here
                # adds overhead and generally wouldn't be a good idea.
                # But I wanted to abstract things out, so that if
                # something can't be imported, all of jako doesn't
                # fail to start.  This should probably be re-done
                # someday.
                modname, funcname = \
                        net_types_readers[self.nettype].rsplit('.', 1)
                mod = importlib.import_module(modname)
                reader = getattr(mod, funcname)
            else:
                reader = getattr(nx, 'read_'+self.nettype)
            g = reader(self.netfile.name)
        g = nx.relabel_nodes(g, dict((x, str(x)) for x in g.nodes_iter()))
        return g
    def del_network(self):
        self.netfile.delete()
        self.netfile = None
        self.save()
    def study_network(self, g=None):
        """Analyze network and store some properties of it.

        g:
            If given, is networkx object and network is not reloaded.
            Just for efficiency reasons."""
        if g is None:
            g = self.get_networkx()
        self.prop_set('nodes', len(g))
        self.prop_set('edges', g.number_of_edges())
        self.prop_set('avgcc', nx.average_clustering(g))
        if all('weight' in d for a,b,d in g.edges_iter(data=True)):
            self.prop_set('weighted', 1)
        elif any('weight' in d for a,b,d in g.edges_iter(data=True)):
            self.prop_set('weighted', 2)
        else:
            self.prop_set('weighted', 0)
    def prop_set(self, name, value):
        DatasetProperties.set(ds=self, generation=self.generation,
                               name=name, value=value)
    def prop_get(self, name):
        return DatasetProperties.get(ds=self, generation=self.generation,
                                     name=name)
    def prop_dict(self):
        return DatasetProperties.getall(ds=self, generation=self.generation)
    def network_properties(self):
        def round2(x):
            return round(x, -int(math.log(x, 10) - 3))
        props2 = self.prop_dict()
        props =  [('number of nodes', int(props2['nodes'])),
                  ('number of edges', int(props2['edges'])),
                  ('avg. clustering coefficient', round2(props2['avgcc'])),
                  ]
        if props2['weighted'] == 1:
            props.append(('weighted edges?', 'yes (all)'),)
        elif props2['weighted'] == 2:
            props.append(('weighted edges?', 'yes (some, but not all)'),)
        elif props2['weighted'] == 0:
            props.append(('weighted edges?', 'no'),)
        return props

    def CD_get(self, cdname, cdgen=None):
        """Return a CD object for this dataset.

        Argument `cdgen` specifies the CD version to get.  If not
        specified, return the latest CD object.  Otherwise, return
        that generation id."""
        if cdgen:
            cd = self.cd_set.get(name=cdname, generation=cdgen)
            return cd
        # Return the latest
        try:
            cd = self.cd_set.filter(name=cdname).order_by('-generation')[0]
            return cd
        except IndexError:
            # IndexError is what you get if no CD exists, since we
            # use slice instead of .get()
            raise CD.DoesNotExist
    def CD_runs(self):
        """Return a list of all the latest CD runs."""
        cd_runs = self.cd_set.order_by('name', '-generation')
        # make a list of only distinct cd runs (by name).  Uses a
        # shortcircuit operator hack to add and return `cd` in the
        # loop element.
        seen = set()
        cd_runs = [ seen.add(cd.name) or cd for cd in cd_runs
                    if cd.name not in seen]
        return cd_runs




class DatasetProperties(models.Model):
    ds = models.ForeignKey(Dataset)
    ds_generation = models.IntegerField()
    name = models.CharField("property name", max_length=32)
    value = models.FloatField()
    #value_str = models.CharField(max_length=32)

    @classmethod
    def set(cls, ds, name, value, generation=None):
        if generation is None:
            generation = ds.generation
        try:
            row = cls.objects.get(ds=ds, ds_generation=generation, name=name)
        except cls.DoesNotExist:
            row = cls(ds=ds, ds_generation=generation, name=name)
        row.value = value
        row.save()
        return row
    @classmethod
    def get(cls, ds, generation, name):
        return cls.objects.get(ds=ds, ds_generation=generation, name=name).value
    @classmethod
    def getall(cls, ds, generation):
        objs = cls.objects.filter(ds=ds, ds_generation=generation)
        return dict((r.name, r.value) for r in objs)


class CD(models.Model):
    name = models.CharField("algorithm class name", max_length=32)
    generation = models.IntegerField(default=0)
    ds = models.ForeignKey(Dataset)
    ds_generation = models.IntegerField()
    state = models.CharField("state", max_length=1)
    btime = models.DateTimeField("birth time", auto_now_add=True)
    mtime = models.DateTimeField("modification time", auto_now=True)
    atime = models.DateTimeField("access time", auto_now=True)
    qtime = models.DateTimeField("time entered queue", null=True)
    rtime = models.DateTimeField("time begin running", null=True)
    dtime = models.DateTimeField("time finished running", null=True)

    options = models.TextField("cd options")
    runtime = models.FloatField("run time", null=True)
    n_layers = models.IntegerField("number of layers", null=True)
    n_cmty = models.TextField("number of nodes", null=True)

    def __unicode__(self):
        return u'<<CD(%s, id=%s, ds=%s, %s)>>'%(self.state, self.id, self.ds.id, self.name)
    def name_pretty(self):
        return cdas.descriptions.get(self.name, self.name)
    def delete(self):
        self.clean_dir()
        super(CD, self).delete()
    def clean_dir(self):
        if os.path.isdir(self.basedir):
            shutil.rmtree(self.basedir)
    @property
    def total_runtime(self):
        return self.dtime - self.rtime

    @property
    def basedir(self):
        return join(self.ds.basedir, self.name)

    def available_options(self, ignore_overridden_opts=False):
        cda = algs.get(self.name)
        options = { }

        # Iterate in order from parent classes (object) to concrete CD
        # class.
        for baseclass in reversed(cda.__mro__):
            # If an option is set (overridden) in a child class, but
            # was documented in a parent class, then that means that
            # this is an explicitely overridden option, and should not
            # be considered free for modification.  In this case,
            # remove it from the options we are returning as
            # modifiable.
            if ignore_overridden_opts:
                for name in tuple(options):
                    if name in baseclass.__dict__:
                        del options[name]
            #
            if baseclass.__doc__:
                options.update(utils.parse_cda_docstring(baseclass))
        #options.update(utils.cda_find_options(cda))

        for name, data in options.items():  # copy so we can delete
            if name.startswith('_'):
                del options[name]
            if name in utils.excluded_options:
                del options[name]
            data['initial'] = getattr(cda, name)
            data['doc'] += '  (default: %s)'%(data['initial'], )
        return options

    @property
    def options_dict(self):
        if self.options:
            return pickle.loads(str(self.options))
        return None
    @options_dict.setter
    def options_dict(self, value):
        self.options = pickle.dumps(value, protocol=0)

    def get_cddoc(self, html=False):
        cda = algs.get(self.name)
        cddoc = [ ]
        for baseclass in cda.__mro__:
            if baseclass.__name__ == 'CDMethod':
                break
            if baseclass.__doc__:
                doc = baseclass.__doc__
                # split docstring by "..." in its own paragraph.
                doc = re.split(r'\n+[ \t]*\n+[ \t]*...\n[ \t]*\n', doc)[0]
                doc = utils.dedent(doc.strip()).strip()
                if html:
                    escape(doc)
                    doc = re.sub(r'((https?|ftps?)://[^\s]+[^\s\.,])',
                                 r'<a href=\1>\1</a>',
                                 doc)
                    doc = mark_safe(doc)
                cddoc.append((baseclass.__name__, doc))
        return cddoc

    def run(self, wait=False):
        self.state = 'Q'
        self.qtime = utcnow()
        self.save()
        from . import queue
        queue.run(which=self)
        if wait is True:
            time.sleep(.5)
            for _ in range(3):
                time.sleep(.5)
                if self.state == 'D':
                    break

    def _run(self):
        self.clean_dir()
        if not os.path.exists(self.basedir):
            os.mkdir(self.basedir)
        # Initialize
        cda = algs.get(self.name)
        g = self.ds.get_networkx()
        self.state = 'R'
        self.save()
        # Do actual running
        self.rtime = utcnow()
        start_time = time.time()
        cd = cda(g, dir=self.basedir, verbosity=-10, **self.options_dict)
        self.dtime = utcnow()
        self.runtime = time.time() - start_time
        # Process results
        self.save_results(cd.results)
        self.state = 'D'
        self.save()

        data = { }
        data['results'] = cd.results
        data['stdout'] = None
        return data

    def save_results(self, results):
        self.n_layers = len(results)
        self.n_cmty = ','.join(str(len(cmtys)) for cmtys in results )
        for i, cmtys in enumerate(results):
            cmtys.write_clusters(join(self.basedir, 'result.%03d.txt'%i))
    def get_results(self):
        results = [ ]
        for i in itertools.count():
            fname = join(self.basedir, 'result.%03d.txt'%i)
            if not exists(fname):
                break
            cmtys = cmty.CommunityFile(fname)
            results.append(cmtys)
        return results


