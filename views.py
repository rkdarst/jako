# Create your views here.

import os.path

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django import forms

import models
from .models import Dataset, CD

from pcd.ioutil import read_any
import pcd.support.algorithms as algs
cdmethods = [name for (name, cda) in vars(algs).iteritems()
             if isinstance(cda, type) and issubclass(cda, algs.CDMethod)
             and not name.startswith('_')]
cdmethods.sort()
algs.global_code_path.insert(0, '/srv/jako/cd-code/')

from . import utils

class CdSession(object):
    netname = None
    id = None
    cdname = None
    meth_options = { }
    def __init__(self):
        import random
        self.id = random.randint(0, 2**32)
        self.init()
    def init(self):
        if not hasattr(self, 'options'):
            self.options = { }

    def set_net(self, name, data):
        self.netname = name
        self.data = data

    def get_net(self):
        if self.netname:
            return self.netname

    def __repr__(self):
        d = dict(self.__dict__)
        if 'data' in d:
            d['data'] = '<<data>>'
        return '%s(%s)'%(self.__class__.__name__, d)

    def get_options(self):
        cda = algs.get(self.cdname)
        options = { }
        initial = { }
        for name in dir(cda):
            if name.startswith('_'):
                continue
            value = getattr(cda, name)
            options[name] = value
        return options
    def set_options(self, cdname, options):
        self.options[cdname] = options
    def run(self):
        tmpdir = '/srv/jako/tmp/%s/'%(self.id, )
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)
        gfname = tmpdir+'graph.txt'
        open(gfname, 'w').write(self.data)
        g = read_any(gfname)
        cda = algs.get(self.cdname)
        cd = cda(g, dir=tmpdir+'/'+self.cdname, **self.options[self.cdname])

        data = { }
        data['results'] = cd.results
        data['stdout'] = None

        return data
    def get_doc(self):
        cda = algs.get(self.cdname)
        for bc in cda.__mro__:
            if bc.__doc__ is not None:
                return bc.__doc__
        return ''

def cd_get_doc(cda):
    for bc in cda.__mro__:
        if bc.__doc__ is not None:
            return bc.__doc__
    return ''


class NetworkForm(forms.Form):
    netfile = forms.FileField(label="Network file",
                              help_text="Select network file to upload or replace existing one.")
    nettype = forms.ChoiceField(label="Network type", choices=models.net_types,
                                help_text="Auto recommended.  Other types are as parsed by networkx.")

class CdNameForm(forms.Form):
    cdname = forms.ChoiceField(label='Method Name',
                                  choices=[(None, '')]+[(x, x) for x in cdmethods])

def index(request):
    session = request.session
    sessionitems = session.items()

    if 'cd' not in session:
        session['cd'] = CdSession()
    cd = session['cd']
    cd.init()

    if request.method == 'POST':
        netform = NetworkForm(request.POST, request.FILES)
        if netform.is_valid():
            f = request.FILES['netfile']
            cd.set_net(f.name, f.read())
    else:
        netform = NetworkForm()

    if request.method == 'POST':
        cdnameform = CdNameForm(request.POST)
        if cdnameform.is_valid() and cdnameform.cleaned_data['cdname'] is not None:
            cdname = cdnameform.cleaned_data['cdname']
            cd.cdname = cdname
    cdnameform = CdNameForm(initial=dict(cdname=cd.cdname))


    # make CD options:
    run = False
    if cd.cdname:
        cddoc = cd.get_doc()
        options = { }
        initial = { }
        for name, value in cd.get_options().iteritems():
            if isinstance(value, bool):
                options[name] = forms.BooleanField(label=name, required=False)
                initial[name] = value
            elif isinstance(value, int):
                options[name] = forms.IntegerField(label=name)
                initial[name] = value
            elif isinstance(value, float):
                options[name] = forms.FloatField(label=name)
                initial[name] = value
            elif isinstance(value, str):
                options[name] = forms.CharField(label=name)
                initial[name] = value

        OptionForm = type('OptionForm', (forms.Form, ), options)
        if request.method == 'POST':
            optionform = OptionForm(request.POST)
            if optionform.is_valid():
                print optionform.cleaned_data
                cd.set_options(cd.cdname, optionform.cleaned_data)
                run = True
            else:
                optionform = OptionForm(initial=initial)
        else:
            optionform = OptionForm(initial=initial)

    # Run CD
    if run:
        data = cd.run()
        results = data['results']
        stdout = data['stdout']
        comm_str = [ ]
        for cmtys in results:
            cmty = [ ]
            cmty.append('# Label: %s'%getattr(cmtys, 'label', ''))
            for cname, cnodes in cmtys.iteritems():
                cmty.append(' '.join(str(n) for n in cnodes))
            comm_str.append('\n'.join(cmty))
            comm_str.append('\n\n\n')
        comm_str = '\n'.join(comm_str)


    sessionitems_end = request.session.items()
    session['cd'] = cd
    context = locals()
    return render(request, 'cd20/cd.html', context)

    #return HttpResponse("Hello, world. You're at the index.")



def main(request):
    return render(request, 'cd20/main.html', locals())

def new(request):
    ds = Dataset()
    ds.save()
    return redirect(dataset, ds.id)

def dataset(request, id):
    id = int(id)
    ds = Dataset.objects.get(id=id)
    if ds.netfile:
        netfile = os.path.basename(ds.netfile.name)

    if request.method == 'POST':
        netform = NetworkForm(request.POST, request.FILES)
        if netform.is_valid():
            f = request.FILES['netfile']
            ds.nettype = netform.cleaned_data['nettype']
            netfile_upload_message = ds.set_graph(f)
            ds.save()
    else:
        netform = NetworkForm(initial={'nettype':ds.nettype})

    # CD methods
    cd_runs = ds.cd_set.all()
    if request.method == 'POST':
        cdnameform = CdNameForm(request.POST)
        if cdnameform.is_valid() and cdnameform.cleaned_data['cdname']:
            cdname = cdnameform.cleaned_data['cdname']
            # Return existing CD run if it exists
            run_cd = ds.cd_set.filter(name=cdname)
            if run_cd:
                return redirect(cdrun, ds.id, run_cd[0].name)
            # Make new CD run
            cd = CD(ds=ds, name=cdname)
            cd.save()
            return redirect(cdrun, ds.id, cdname)
    cdnameform = CdNameForm()

    print cd_runs

    #from fitz import interactnow


    return render(request, 'cd20/dataset.html', locals())


def cdrun(request, did, cdname):
    did = int(did)
    ds = Dataset.objects.get(id=did)
    cd = ds.cd_set.get(name=cdname)
    if ds.netfile:
        netfile = os.path.basename(ds.netfile.name)

    cddoc = cd.get_cddoc()

    run = False

    # Make the options form
    options = { }
    initial = { }
    for name, d in cd.available_options().iteritems():
        value = d['value']
        if isinstance(value, bool):
            options[name] = forms.BooleanField(label=name, required=False,
                                               help_text=d['doc'])
            initial[name] = value
        elif isinstance(value, int):
            options[name] = forms.IntegerField(label=name,
                                               help_text=d['doc'])
            initial[name] = value
        elif isinstance(value, float):
            options[name] = forms.FloatField(label=name,
                                             help_text=d['doc'])
            initial[name] = value
        elif d['type'] == 'list(float)':
            print name, value
            options[name] = utils.ListField(label=name, type=float,
                                            help_text=d['doc'])
            initial[name] = value
        elif isinstance(value, str):
            options[name] = forms.CharField(label=name,
                                            help_text=d['doc'])
            initial[name] = value

    OptionForm = type('OptionForm', (forms.Form, ), options)
    if request.method == 'POST':
        optionform = OptionForm(request.POST)
        if optionform.is_valid():
            print optionform.cleaned_data
            cd.options_dict = optionform.cleaned_data
            run = True
        else:
            pass
    else:
        optionform = OptionForm(initial=initial)

    # Run CD
    if run:
        data = cd.run()
        #results = data['results']
        #stdout = data['stdout']


    if cd.state == 'D':
        results = cd.get_results()
        comm_str = [ ]
        for cmtys in results:
            cmty = [ ]
            cmty.append('# Label: %s'%getattr(cmtys, 'label', ''))
            for cname, cnodes in cmtys.iteritems():
                cmty.append(' '.join(str(n) for n in cnodes))
            comm_str.append('\n'.join(cmty))
            comm_str.append('\n\n\n')
        comm_str = '\n'.join(comm_str)



    return render(request, 'cd20/cdrun.html', locals())
