import datetime
import itertools
import logging
import os
from os.path import join, exists
import cPickle as pickle
import random
import shutil
import time

from django.db import models
from django.core.files.storage import Storage

import networkx as nx
import pcd.support.algorithms as algs
import pcd.cmty as cmty
from pcd.ioutil import read_any
algs.global_code_path.insert(0, '/srv/jako/cd-code/')

from .config import *
from . import utils

logger = logging.getLogger(__name__)

# Create your models here.

rootdir = '/mnt/data1/srv/jako/tmp/'
def netfile_upload_to(instance, filename):
    path = join(instance.basedir, filename)
    return path

def new_ds_id():
    while True:
        id = random.randint(1, 2**16-1)
        if Dataset.objects.filter(id=id):
            continue
        return id

net_types = [
    ('auto', 'Auto (edgelist, GML, Pajek)'),
    ('adjlist', 'Adjacency list'),
    ('multiline_adjlist', 'Multiline Adjacency list'),
    ('edgelist', 'Edge list'),
    ('gexf', 'GEXF'),
    ('gml', 'GML'),
    ('graphml', 'GraphML'),
    ('pajek', 'Pajek'),
    ('yaml', 'YAML'),
    ]



class Dataset(models.Model):
    id = models.AutoField(primary_key=True, default=new_ds_id)
    btime = models.DateTimeField("birth time", auto_now_add=True)
    mtime = models.DateTimeField("modification time", auto_now=True)
    atime = models.DateTimeField("access time", auto_now=True)
    netfile = models.FileField(upload_to=netfile_upload_to)
    nettype = models.CharField(max_length=10,
                               choices=net_types, default='auto')

    nodes = models.IntegerField("number of nodes", null=True)
    edges = models.IntegerField("number of edges", null=True)
    clustc = models.FloatField("clustering coef", null=True)
    weighted = models.IntegerField("clustering coef", null=True)

    def __unicode__(self):
        if self.netfile:
            return u'<<Dataset(ds=%s, %s)>>'%(self.id, os.path.basename(self.netfile.name))
        return u'<<Dataset(ds=%s)>>'%(self.id, )
    def delete(self):
        shutil.rmtree(self.basedir)
        super(CD, self).delete()

    @property
    def basedir(self):
        id = self.id
        if id is None:
            raise Exception("no ID")
        dir = join(rootdir, str(id))
        if not exists(dir):
            os.mkdir(dir)
        return dir

    # This function should be abstracted out later
    def get_network_limits(self):
        """Get size limits of uploaded networks."""
        return dict(bytes=MAX_NETWORK_BYTES, nodes=MAX_NETWORK_NODES,
                    edges=MAX_NETWORK_EDGES)
    def set_network(self, f):
        """User has uploaded a graph, save and sanity check it"""
        limits = self.get_network_limits()
        # Check size
        if f.size > limits['bytes']:
            netfile_upload_message = "Upload failed, network is too big"
            return netfile_upload_message
        # Do actual saving of network.
        if self.netfile:
            self.del_network()
        self.netfile = f
        netfile_upload_message = "Successfully uploaded %s"%f.name
        self.save()
        # Make sure that network can be loaded
        try:
            g = self.get_networkx()
        except Exception as e:
            self.del_network()
            netfile_upload_message = 'Upload failed, network not openable (%s, %s)'%(self.nettype, e)
            return netfile_upload_message
        # Check nodes/edges limits...
        if len(g) > limits['nodes']:
            return 'Upload failed, too many nodes in network.'
        if g.number_of_edges() > limits['edges']:
            self.del_network()
            return 'Upload failed, too many edges in network.'
        # Run and save basic network statistics.
        self.study_network(g)
        return netfile_upload_message

    def get_networkx(self):
        if self.nettype == 'auto':
            g = read_any(self.netfile.name)
        else:
            g = getattr(nx, 'read_'+self.nettype)(self.netfile.name)
        g = nx.relabel_nodes(g, dict((x, str(x)) for x in g.nodes_iter()))
        return g
    def del_network(self):
        self.netfile.delete()
        self.netfile = None
        self.nodes = None
        self.edges = None
        self.clustc = None
        self.save()
    def study_network(self, g=None):
        """Analyze network and store some properties of it.

        g:
            If given, is networkx object and network is not reloaded.
            Just for efficiency reasons."""
        if g is None:
            g = self.get_networkx()
        self.nodes = len(g)
        self.edges = g.number_of_edges()
        self.clustc = nx.average_clustering(g)
        if all('weight' in d for a,b,d in g.edges_iter(data=True)):
            self.weighted = 1
        elif any('weight' in d for a,b,d in g.edges_iter(data=True)):
            self.weighted = 2
        else:
            self.weighted = 0


class CD(models.Model):
    name = models.CharField("algorithm class name", max_length=32)
    ds = models.ForeignKey(Dataset)
    state = models.CharField("", max_length=1)
    btime = models.DateTimeField("birth time", auto_now_add=True)
    mtime = models.DateTimeField("modification time", auto_now=True)
    atime = models.DateTimeField("access time", auto_now=True)
    qtime = models.DateTimeField("time entered queue", null=True)
    rtime = models.DateTimeField("time begin running", null=True)
    dtime = models.DateTimeField("time finished running", null=True)

    options = models.TextField("cd options")
    runtime = models.FloatField("cd options", null=True)
    n_layers = models.IntegerField("number of layers", null=True)
    n_cmty = models.TextField("number of nodes", null=True)

    def __unicode__(self):
        return u'<<CD(%s, id=%s, ds=%s, %s)>>'%(self.state, self.id, self.ds.id, self.name)
    def delete(self):
        self.clean_dir()
        super(CD, self).delete()
    def clean_dir(self):
        if os.path.isdir(self.basedir):
            shutil.rmtree(self.basedir)

    @property
    def basedir(self):
        return join(self.ds.basedir, self.name)

    def available_options(self):
        cda = algs.get(self.name)
        options = { }
        initial = { }
        for name in dir(cda):
            if name.startswith('_'):
                continue
            if name in set(('verbosity',)):
                continue
            value = getattr(cda, name)
            doc = getattr(cda, '_%s_doc'%name, "")+("  (default: %s)"%(value, ))
            options[name] = dict(value=value,
                                 doc=doc,
                                 type=getattr(cda, '_%s_type'%name, None))
        return options

    @property
    def options_dict(self):
        if self.options:
            return pickle.loads(str(self.options))
        return None
    @options_dict.setter
    def options_dict(self, value):
        self.options = pickle.dumps(value, protocol=0)

    def get_cddoc(self):
        cda = algs.get(self.name)
        for bc in cda.__mro__:
            if bc.__doc__ is not None:
                return utils.dedent(bc.__doc__)
        return ''

    def run(self):
        self.state = 'Q'
        self.qtime = datetime.datetime.now()
        self.save()
        from . import queue
        return queue.run(which=self)

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
        self.rtime = datetime.datetime.now()
        start_time = time.time()
        cd = cda(g, dir=self.basedir, verbosity=-10, **self.options_dict)
        self.dtime = datetime.datetime.now()
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


