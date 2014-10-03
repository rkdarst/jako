# Create your views here.

from functools import partial
import json
import logging
import os.path

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django import forms
from django.contrib import messages

import networkx as nx
from pcd.ioutil import read_any
import pcd.support.algorithms as algs

from .config import *
from . import models
from .models import Dataset, CD
from . import utils

logger = logging.getLogger(__name__)


class NetworkForm(forms.Form):
    netfile = forms.FileField(label="Network file",
                              help_text="Select network file to upload or to replace existing network.  "
                              "Any old network will be lost."
                              )
    nettype = forms.ChoiceField(label="Network type", choices=models.net_types,
                                help_text='Different formats are read by the <a href="http://networkx.github.io/documentation/networkx-1.9/reference/readwrite.html"><i>read_*</i> '
                                'functions in networkx</a>.')

import types
def as_table2(self):
    return self._html_output(
        #normal_row = u'<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s</td></tr><tr><td style="padding-bottom:25px;" colspan="2">%(help_text)s</td></tr>',
        normal_row = u'<tr%(html_class_attr)s"><th>%(label)s</th><td>%(errors)s%(field)s</td><td>%(help_text)s</td></tr>',
        error_row = u'<tr><td colspan="3">%s</td></tr>',
        row_ender = u'</td></tr>',
        help_text_html = u'<span class="helptext">%s</span>',
        errors_on_separate_row = False)
import types
forms.BaseForm.as_table = types.MethodType(as_table2, None, forms.BaseForm)

class CdNameForm(forms.Form):
    cdname = forms.ChoiceField(label='Method Name',
                                  choices=[(None, '<select>')]+[(x, x) for x in CDMETHODS])




def main(request):
    return render(request, 'cd20/main.html', locals())



def new(request):
    if request.method == "POST":
        ds = Dataset()
        ds.save()
        messages.success(request, "New dataset %s created."%ds.name())
        return redirect(dataset, ds.id)
    return redirect(main)



def dataset(request, id):
    id = int(id)
    ds = Dataset.objects.get(id=id)
    breadcrumbs = ((reverse(main), 'Home'),
                   (None, 'Dataset %s'%id))

    if request.method == 'POST':
        netform = NetworkForm(request.POST, request.FILES)
        if netform.is_valid():
            f = request.FILES['netfile']
            ds.nettype = netform.cleaned_data['nettype']
            netfile_upload_message = ds.set_network(
                f, messenger=partial(messages.add_message, request))
            ds.save()
            #messages.success(request, "Network file updated.")
            return redirect(dataset, id)
    else:
        netform = NetworkForm(initial={'nettype':ds.nettype})

    # CD methods
    cd_runs = ds.cd_set.all()
    if request.method == 'POST':
        cdnameform = CdNameForm(request.POST)
        if cdnameform.is_valid() and cdnameform.cleaned_data['cdname'] \
               and cdnameform.cleaned_data['cdname']!=u'None':
            cdname = cdnameform.cleaned_data['cdname']
            # Return existing CD run if it exists
            run_cd = ds.cd_set.filter(name=cdname)
            if run_cd:
                return redirect(cdrun, ds.id, run_cd[0].name)
            # Make new CD run
            cd = CD(ds=ds, name=cdname)
            cd.save()
            messages.success(request, "Created CD run %s on dataset %s."%(cdname, ds.name()))
            return redirect(cdrun, ds.id, cdname)
    cdnameform = CdNameForm()

    return render(request, 'cd20/dataset.html', locals())



def cdrun(request, did, cdname):
    did = int(did)
    ds = Dataset.objects.get(id=did)
    try:
        cd = ds.cd_set.get(name=cdname)
    except CD.DoesNotExist:
        return HttpResponse("CD run does not exist", status=404)
    if ds.netfile:
        netfile = os.path.basename(ds.netfile.name)
    breadcrumbs = ((reverse(main), 'Home'),
                   (reverse(dataset, args=(did, )), 'Dataset %s'%did),
                   (None, cdname),
                   )

    cddoc = cd.get_cddoc(html=True) # list of (name, docstring) tuples

    run = False

    # Make the options form
    options = { }
    initials = { }
    for name, d in cd.available_options().iteritems():
        initial = d['initial']
        if d['type'] == 'int, optional':
            options[name] = forms.IntegerField(label=name, help_text=d['doc'], required=False)
            initials[name] = initial
        elif d['type'] == 'int':
            options[name] = forms.IntegerField(label=name, help_text=d['doc'])
            initials[name] = initial

        elif d['type'] == 'float, optional':
            options[name] = forms.FloatField(label=name, help_text=d['doc'], required=False)
            initials[name] = initial
        elif d['type'] == 'float':
            options[name] = forms.FloatField(label=name, help_text=d['doc'])
            initials[name] = initial

        elif d['type'] == 'bool':
            options[name] = forms.BooleanField(label=name, help_text=d['doc'], required=False)
            initials[name] = initial


        elif d['type'] == 'list(float)' or d['type'] == 'list of float':
            options[name] = utils.ListField(label=name, type=float,
                                            help_text=d['doc'])
            initials[name] = initial
        elif isinstance(initial, bool):
            options[name] = forms.BooleanField(label=name, required=False,
                                               help_text=d['doc'])
            initials[name] = initial
        elif isinstance(initial, int):
            options[name] = forms.IntegerField(label=name,
                                               help_text=d['doc'])
            initials[name] = initial
        elif isinstance(initial, float):
            options[name] = forms.FloatField(label=name,
                                             help_text=d['doc'])
            initials[name] = initial
        elif isinstance(initial, str):
            options[name] = forms.CharField(label=name,
                                            help_text=d['doc'])
            initials[name] = initial

    OptionForm = type('OptionForm', (forms.Form, ), options)
    if request.method == 'POST':
        optionform = OptionForm(request.POST)
        if optionform.is_valid():
            cd.options_dict = optionform.cleaned_data
            run = True
        else:
            messages.error(request, "Invalid options given.")
    else:
        if cd.options_dict:
            initials.update(cd.options_dict)
        optionform = OptionForm(initial=initials)

    # Run CD
    if run:
        data = cd.run(wait=True)
        cd = ds.cd_set.get(name=cdname)
        if cd.state == 'D':
            messages.success(request, "CD run complete.")
        elif cd.state in 'QR':
            messages.info(request, "CD run submitted.")
        else:
            messages.info(request, "CD run: error: state is %s"%cd.state)
        return redirect(cdrun, did, cdname)

    if cd.state == 'D':
        results = cd.get_results()
        download_formats_ = download_formats  # make local variable
        if cd.ds.nodes < 500:
            comm_str = [ ]
            for cmtys in results:
                cmty = [ ]
                cmty.append('# Label: %s'%getattr(cmtys, 'label', ''))
                for cname, cnodes in cmtys.iteritems():
                    cmty.append(' '.join(str(n) for n in cnodes))
                comm_str.append('\n'.join(cmty))
            comm_str = '\n\n\n\n'.join(comm_str)

    return render(request, 'cd20/cdrun.html', locals())



def cmtys(request):
    pass



def cmtys_viz(request, did, cdname, layer, ext=None):
    """Interactively visualize communities.

    Based on http://bl.ocks.org/mbostock/4062045
    """
    did = int(did)
    ds = Dataset.objects.get(id=did)
    cd = ds.cd_set.get(name=cdname)
    breadcrumbs = ((reverse(main), 'Home'),
                   (reverse(dataset, args=(did, )), 'Dataset %s'%did),
                   (reverse(cdrun, args=(did, cdname)), cdname),
                   (None, "Visualize")
                   )

    cmtys = cd.get_results()[int(layer)]
    graphjsonname = 'viz.json'

    if ext == '.json':
        g = ds.get_networkx()
        nodecmtys = cmtys.nodecmtys()

        data = { }
        nodes = data['nodes'] = [ ]
        links = data['links'] = [ ]

        node_map = dict((n, i) for i, n in enumerate(g.nodes_iter()))

        for n in g.nodes_iter():
            c = nodecmtys.get(n, ('None',))
            c = ','.join(str(x) for x in c)
            color = c
            nodes.append(dict(name="%s (%s)"%(n, c), group=color))
        for a,b in g.edges_iter():
            links.append(dict(source=node_map[a], target=node_map[b], value=1))
        data = json.dumps(data)
        return HttpResponse(content=data, content_type='text/plain', )

    return render(request, 'cd20/cmtys_viz.html', locals())



download_formats = [
    ('txt', 'One line per community'),
    ('clu', '(node cmty) pairs'),
    ('gexf', 'GEXF graph with "cmty" attribute'),
    ('gml', 'GML graph with "cmty" attribute'),
    ]
def download_cmtys(request, did, cdname, layer, format):
    did = int(did)
    ds = Dataset.objects.get(id=did)
    cd = ds.cd_set.get(name=cdname)

    fname_requested = format
    format = format.rsplit('.')[-1]

    fname = '%s-%s%s.%s'%(os.path.basename(ds.netfile.name), cdname, layer, format)
    if fname_requested != fname:
        return redirect(download_cmtys, did=did, cdname=cdname, layer=layer,
                        format=fname)

    cmtys = cd.get_results()[int(layer)]

    data = [ ]
    content_type = 'text/plain'
    force_download = False
    if format == 'txt':
        for cname, cnodes in cmtys.iteritems():
            data.append(' '.join(str(x) for x in cnodes))
        data = '\n'.join(data)
    elif format == 'clu':
        for cname, cnodes in cmtys.iteritems():
            for node in cnodes:
                data.append('%s %s'%(node, cname))
        data = '\n'.join(data)
    elif format == 'gexf':
        g = ds.get_networkx()
        for node, cs in cmtys.nodecmtys().iteritems():
            g.node[node]['cmty'] = ' '.join(str(x) for x in cs)
        data = nx.generate_gexf(g)
        data = '\n'.join(data)
    elif format == 'gml':
        g = ds.get_networkx()
        for node, cs in cmtys.nodecmtys().iteritems():
            g.node[node]['cmty'] = ','.join(str(x) for x in cs)
        data = nx.generate_gml(g)
        data = '\n'.join(data)

    response = HttpResponse(content=data, content_type=content_type, )
    # If the data size is too big, force a download instead of viewing as text.
    if force_download or len(data) > 50 * 2**10:
        response['Content-Disposition'] = 'attachment; filename=%s'%fname
    return response


def cmtys_draw(request, did, cdname, layer, ext):
    did = int(did)
    ds = Dataset.objects.get(id=did)
    cd = ds.cd_set.get(name=cdname)

    import matplotlib ; matplotlib.use('Agg')
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure

    dpi = 96
    fig = Figure(figsize=(8, 5), dpi=dpi)
    canvas = FigureCanvas(fig)
    #ax = fig.add_subplot(111)
    ax = fig.add_axes([0, 0, 1, 1])

    g = ds.get_networkx()
    cmtys = cd.get_results()[int(layer)]
    nodecolors = cmtys.nodecolors()

    # Do actual plotting.
    nodelist = g.nodes()
    nodecolors = [nodecolors[n] for n in nodelist]
    import nxdraw_without_pylab
    nxdraw_without_pylab.draw_networkx(g, ax=ax, with_labels=True, node_color=nodecolors, nodelist=nodelist)
    ax.set_axis_off()

    # Manually compute the bbox in order to get a tight layout.
    bbox = ax.collections[0].get_window_extent(fig)  # patches
    #bbox = ax.collections[1].get_window_extent(ax)  # lines
    from matplotlib.transforms import TransformedBbox, Affine2D
    bbox2 = TransformedBbox(bbox, Affine2D().scale(1. / dpi))
    #from fitz import interactnow
    bbox._points[0] -= .15 * dpi
    bbox._points[1] += .15 * dpi

    # Save the figure to an in-memory StringIO and return it.
    import cStringIO
    p = cStringIO.StringIO()
    canvas.print_figure(p, format='pdf', bbox_inches=bbox2) #bbox_inches='tight')
    response = HttpResponse(p.getvalue(), mimetype="application/pdf")
    return response


def cmtys_stdout(request, did, cdname, ext=None):
    """Show raw standard output of CD runs.
    """
    did = int(did)
    ds = Dataset.objects.get(id=did)
    cd = ds.cd_set.get(name=cdname)
    breadcrumbs = ((reverse(main), 'Home'),
                   (reverse(dataset, args=(did, )), 'Dataset %s'%did),
                   (reverse(cdrun, args=(did, cdname)), cdname),
                   (None, "Raw output")
                   )

    outputs = [ ]
    for fname in os.listdir(cd.basedir):
        if not fname.endswith('.stdout'):
            continue
        outputs.append((fname, open(os.path.join(cd.basedir, fname)).read()))

    return render(request, 'cd20/cmtys_stdout.html', locals())
