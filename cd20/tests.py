"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

import os
import re
import shutil

from django.test import TestCase
from django.test.utils import override_settings

from . import models
from . import utils

# This is needed to have the queue running be done in the same process
# (to use the test DB), instead of spawning a new process (and thus
# using the production DB) which was recently made the default.
from . import queue
queue.spawn_queue = queue.run

class _TmpRoot(object):
    @classmethod
    def setUpClass(cls):
        from . import config, models
        cls.ROOTDIR = config.ROOTDIR+'/test-base/'
        config.ROOTDIR_OLD = config.ROOTDIR
        config.ROOTDIR = models.ROOTDIR = cls.ROOTDIR
        os.mkdir(config.ROOTDIR)
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ROOTDIR)
        from . import config, models
        config.ROOTDIR = models.ROOTDIR = config.ROOTDIR_OLD


class BasicTest(_TmpRoot, TestCase):

    def test_basic(self):
        self.client.get('/')
        #self.client.get('/dataset/20/')
        self.assertRaises(Exception, self.client.get, '/dataset/20/')

        # Make test dataset
        ds = models.Dataset(id=20)
        ds.save()
        r = self.client.get('/dataset/20/')
        #print r.content
        self.assertContains(r, u'New dataset', )
        #assert 'Current network: None.' in r.content

        ds.netfile = utils.get_graph_file('data/karate.gml')
        r = self.client.post('/dataset/20/',
                             dict(netfile=utils.get_graph_file('data/karate.gml'),
                                  nettype='auto'), follow=True)
        self.assertContains(r, u'karate.gml')
        r = self.client.get('/dataset/20/')
        self.assertContains(r, u'karate.gml')

        cdname = 'Infomap'
        r = self.client.post('/dataset/20/',
                             dict(cdname=cdname))
        self.assertRedirects(r, '/dataset/20/%s/'%cdname, status_code=302)

        r = self.client.get('/dataset/20/%s/'%cdname)
        self.assertContains(r, cdname)
        self.assertContains(r, "state: ''")

        # Run CD
        r = self.client.post('/dataset/20/%s/'%cdname,
                             dict(weighted=False, max_overlap=1, trials=10))
        #self.assertContains(r, 'state: D')
        #print r.content
        r = self.client.get('/dataset/20/%s/'%cdname)

        self.assertContains(r, "state: 'D'")

        # Test that method appears in the "done" list.
        r = self.client.get('/dataset/20/')
        self.assertTrue(re.search(r'Existing.*%s'%cdname, r.content,
                                  re.DOTALL))

class TestFormats(_TmpRoot, TestCase):
    formats = (('gml', 'data/karate.gml'),
               ('jsonD3nl', 'data/karate_club.d3-node-link'),
               ('jsonD3a', 'data/karate_club.d3-adj'),
               )
    def test(self):
        for nettype, fname in self.formats:
            self._do_test(nettype, fname)
    def _do_test(self, nettype, fname):
        ds = models.Dataset()
        did = ds.id
        ds.save()
        r = self.client.get('/dataset/%s/'%did)
        #ds.netfile = utils.get_graph_file(fname)

        r = self.client.post('/dataset/%s/'%did,
                             dict(netfile=utils.get_graph_file(fname),
                                  nettype=nettype), follow=True)
        #r = self.client.get('/dataset/20/')
        self.assertContains(r, os.path.basename(fname))
        ds = models.Dataset.objects.get(id=did)
        #print ds.prop_dict()
        self.assertEqual(34, ds.prop_get('nodes'), (nettype, fname))
        self.assertEqual(78, ds.prop_get('edges'), (nettype, fname))



class TestAlgs(TestCase):
  def test_algs(self):
    from pcd.support import algorithms as algs
    from cd20.utils import parse_cda_docstring
    parse_cda_docstring(algs.Infomap)
