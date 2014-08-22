import textwrap

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
