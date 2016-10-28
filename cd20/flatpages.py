import os
from os.path import join

from django.shortcuts import render, redirect


basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
basedir = os.path.join(basedir, 'jako/pages')

from django.template import Template, RequestContext
#from django.template.loader import get_template, find_template, get_template_from_string
from django.http import HttpResponse

def view_flat(request, pagename):
    """Minimal flat pages view

    Custom-load templates from the jako/pages/ directory, and use this
    to render 'static' pages."""
    pagetitle = title = pagename.title()
    return render(request, pagename+'.html', locals())
