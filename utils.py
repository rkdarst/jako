import os
from os.path import dirname, join
import re
import textwrap

from django.core.files.base import ContentFile

def dedent(s):
    """Like textwrap.dedent, but skips the first line.

    This is needed for docstrings"""
    s = s.split('\n')
    s = '\n'.join((s[0], textwrap.dedent('\n'.join(s[1:]))))
    return s


from django.forms import CharField, ValidationError

class ListField(CharField):
    def __init__(self, type, *args, **kwargs):
        self._type = type
        super(ListField, self).__init__(*args, **kwargs)
    def prepare_value(self, value):
        if isinstance(value, (str, unicode)):
            return value
        val = ', '.join(str(x) for x in value)
        return val
    def to_python(self, s):
        print 'to_python', repr(s), type(s)
        data = s.split(',')
        try:
            return [ self._type(x) for x in data ]
        except ValueError as e:
            raise ValidationError("Invalid type: %s"%e)



def get_graph_file(path, name=None):
    """Get graph file in Django object for testing purposes"""
    fname = join(dirname(__file__), path)
    # We must use ContentFile to avoid SuspiciousOperation errors.
    # We read the data outside of django and pass it as a string.
    f = ContentFile(open(fname).read())
    if name is None:
        name = os.path.basename(path)
    f.name = name
    f.path = name
    return f
def set_graph_file(ds, f):
    if ds.netfile: ds.netfile.delete()
    ds.set_network(f)


excluded_options = set()
#excluded_options = set(('verbosity', 'directed'))

def cda_get_doc(cda):
    for bc in cda.__mro__:
        if bc.__doc__ is not None:
            return bc.__doc__
    return ''

def cda_find_options(cda):
    options = { }
    initial = { }
    for name in dir(cda):
        initial = getattr(cda, name)
        doc = getattr(cda, '_%s_doc'%name, "")+("  (default: %s)"%(initial, ))
        options[name] = dict(initial=initial,
                             doc=doc,
                             type=getattr(cda, '_%s_type'%name, None))
    return options

def parse_cda_docstring(cda):
    item_re = re.compile(r'''^\s*(?P<name>\w+):[ ]?(?P<type>[\w ,]+)\n
    (?P<doc>
        ([^\n]+\n)+
    )

    ''', re.VERBOSE|re.MULTILINE)
    docstring = cda_get_doc(cda)

    options = { }
    items = item_re.finditer(docstring)
    for m in items:
        name = m.group('name')
        if not hasattr(cda, name):
            continue
        initial = getattr(cda, name)
        type_ = m.group('type')
        doc = m.group('doc')
        doc = re.sub(r'^[ \t]+', ' ', doc, flags=re.MULTILINE).strip()
        doc = "%s %s"%(doc, ("  (default: %s)"%(initial, )))

        options[name] = dict(initial=initial,
                             doc=doc,
                             type=type_)
    return options
