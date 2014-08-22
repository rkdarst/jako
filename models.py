import itertools
import os
from os.path import join, exists
import cPickle as pickle
import random
import time

from django.db import models
from django.core.files.storage import Storage

import networkx as nx
import pcd.support.algorithms as algs
import pcd.cmty as cmty
from pcd.ioutil import read_any

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

    @property
    def basedir(self):
        id = self.id
        if id is None:
            raise Exception("no ID")
        dir = join(rootdir, str(id))
        if not exists(dir):
            os.mkdir(dir)
        return dir

    def set_graph(self, f):
        if self.netfile is not None:
            self.netfile.delete()
            self.save()
        self.netfile = f
        netfile_upload_message = "Successfully uploaded %s"%f.name
        self.save()
        try:
            g = self.get_networkx()
        except Exception as e:
            netfile_upload_message = 'upload failed (%s, %s)'%(self.nettype, e)
        self.study_network(g)
        return netfile_upload_message

    def get_networkx(self):
        if self.nettype == 'auto':
            g = read_any(self.netfile.name)
        else:
            g = getattr(nx, 'read_'+self.nettype)(self.netfile.name)
        return g
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

    options = models.TextField("cd options")
    runtime = models.FloatField("cd options", null=True)
    n_layers = models.IntegerField("number of layers", null=True)
    n_cmty = models.TextField("number of nodes", null=True)

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
            value = getattr(cda, name)
            options[name] = value
        return options

    @property
    def options_dict(self):
        return pickle.loads(self.options)
    @options_dict.setter
    def options_dict(self, value):
        self.options = pickle.dumps(value, protocol=0)

    def get_cddoc(self):
        cda = algs.get(self.name)
        for bc in cda.__mro__:
            if bc.__doc__ is not None:
                return bc.__doc__
        return ''

    def run(self):
        if not os.path.exists(self.basedir):
            os.mkdir(self.basedir)
        self.state = 'R'
        self.save()

        start_time = time.time()
        cda = algs.get(self.name)
        g = self.ds.get_networkx()
        cd = cda(g, dir=self.basedir, **self.options_dict)
        self.runtime = time.time() - start_time
        self.save_results(cd.results)
        self.state = 'D'
        self.save()

        data = { }
        data['results'] = cd.results
        data['stdout'] = None
        return data

    def save_results(self, results):
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

