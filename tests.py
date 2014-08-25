"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

import os
import shutil

from django.test import TestCase
from django.test.utils import override_settings

from . import models
from . import utils

class BasicTest(TestCase):
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

    def test_basic(self):
        self.client.get('/')
        #self.client.get('/dataset/20/')
        self.assertRaises(Exception, self.client.get, '/dataset/20/')

        # Make test dataset
        ds = models.Dataset(id=20)
        ds.save()
        r = self.client.get('/dataset/20/')
        #print r.content
        self.assertContains(r, u'Current network: None.', )
        assert 'Current network: None.' in r.content

        ds.netfile = utils.get_graph_file('data/karate.gml')
        r = self.client.post('/dataset/20/',
                             dict(netfile=utils.get_graph_file('data/karate.gml'),
                                  nettype='auto'))
        self.assertContains(r, u'karate.gml')
        r = self.client.get('/dataset/20/')
        self.assertContains(r, u'karate.gml')

        r = self.client.post('/dataset/20/',
                             dict(cdname='Copra'))
        self.assertRedirects(r, '/dataset/20/Copra/', status_code=302)

        r = self.client.get('/dataset/20/Copra/')
        self.assertContains(r, 'Copra')
        self.assertContains(r, 'not completed')

        # Run CD
        r = self.client.post('/dataset/20/Copra/',
                             dict(weighted=False, max_overlap=1, trials=10))
        #self.assertContains(r, 'state: D')
        #print r.content
        r = self.client.get('/dataset/20/Copra/')

        self.assertContains(r, 'state: D')
