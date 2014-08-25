import os
from os.path import dirname, join
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
