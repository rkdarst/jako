import textwrap

def dedent(s):
    """Like textwrap.dedent, but skips the first line.

    This is needed for docstrings"""
    s = s.split('\n')
    s = '\n'.join((s[0], textwrap.dedent('\n'.join(s[1:]))))
    return s
