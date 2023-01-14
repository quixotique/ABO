# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Text processing utilities.
"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.text
    doctest.testmod(abo.text)

def number_lines(lines, name=None, start=1):
    '''Iterate over the given lines, transforming them into numbered_line
    objects with name and line_number attributes.  Interpret input lines
    starting with "#line " specially.
    >>> nl = list(number_lines(['a', 'b', '#line 8 bar', 'c'], name='foo'))
    >>> len(nl)
    3
    >>> nl[0]
    'a'
    >>> nl[0].line_number
    1
    >>> nl[0].name
    'foo'
    >>> nl[2]
    'c'
    >>> nl[2].line_number
    8
    >>> nl[2].name
    'bar'
    '''
    if name is None and hasattr(lines, 'name'):
        name = lines.name
    lnum = 0
    for line in lines:
        lnum += 1
        if line.startswith('#line '):
            words = line[6:].lstrip().split(None, 2)
            if len(words) >= 1 and words[0].isdigit():
                lnum = int(words[0]) - 1
                if len(words) >= 2:
                    name = words[1]
        else:
            nline = numbered_line(line)
            nline.line_number = lnum
            nline.name = name
            yield nline

class numbered_line(str):

    r'''Sub-class of str which carries extra attributes such as 'line_number'
    and 'name', which it preserves where needed.

    >>> i = numbered_line(' abc ')
    >>> i.line_number = 42
    >>> i.name = 'wah'
    >>> i.lstrip()
    'abc '
    >>> type(i.lstrip())
    <class 'abo.text.numbered_line'>
    >>> i.lstrip().line_number
    42
    >>> i.lstrip().name
    'wah'
    >>> i.rstrip()
    ' abc'
    >>> type(i.rstrip())
    <class 'abo.text.numbered_line'>
    >>> i.rstrip().line_number
    42
    >>> i.rstrip().name
    'wah'
    >>> i[2]
    'b'
    >>> i[2].name
    'wah'
    >>> i[3:]
    'c '
    >>> i[3:].name
    'wah'
    >>> i + 'def'
    ' abc def'
    >>> (i + 'def').name
    'wah'
    >>> 'xxx' + i
    'xxx abc '
    >>> ('xxx' + i).name
    'wah'

    >>> j = numbered_line('a b cde fgh ')
    >>> j.name = 'wah'
    >>> j.split(None, 2)
    ['a', 'b', 'cde fgh ']
    >>> j.split(None, 2)[2].name
    'wah'

    Cannot pickle instances of numbered_line:

    >>> import abo.text
    >>> i = abo.text.numbered_line('xyz')
    >>> import pickle
    >>> pickle.dumps(i, 0)
    Traceback (most recent call last):
    _pickle.PicklingError: cannot pickle 'xyz' with type <class 'abo.text.numbered_line'>
    >>> pickle.dumps(i, 1)
    Traceback (most recent call last):
    _pickle.PicklingError: cannot pickle 'xyz' with type <class 'abo.text.numbered_line'>
    >>> pickle.dumps(i, 2)
    Traceback (most recent call last):
    _pickle.PicklingError: cannot pickle 'xyz' with type <class 'abo.text.numbered_line'>

    '''

    def __new__(cls, arg=''):
        if isinstance(arg, cls):
            return arg
        self = super(numbered_line, cls).__new__(cls, arg)
        if isinstance(arg, cls):
            self.__dict__.update(arg.__dict__)
        return self

    def __getstate__(self):
        import pickle
        raise pickle.PicklingError('cannot pickle %r with type %r' % (self, type(self)))

    def __getnewargs__(self):
        import pickle
        raise pickle.PicklingError('cannot pickle %r with type %r' % (self, type(self)))

    def __wrap(self, value):
        obj = type(self)(value)
        obj.__dict__.update(self.__dict__)
        return obj

    def strip(self, chars=None):
        return self.__wrap(super(numbered_line, self).strip(chars))

    def rstrip(self, chars=None):
        return self.__wrap(super(numbered_line, self).rstrip(chars))

    def lstrip(self, chars=None):
        return self.__wrap(super(numbered_line, self).lstrip(chars))

    def __getitem__(self, key):
        return self.__wrap(super(numbered_line, self).__getitem__(key))

    def __getslice__(self, i, j):
        return self.__wrap(super(numbered_line, self).__getslice__(i, j))

    def __add__(self, other):
        return self.__wrap(super(numbered_line, self).__add__(other))
        
    def __radd__(self, other):
        return self.__wrap(other.__add__(self))

    def split(self, *args):
        return list(map(self.__wrap, super(numbered_line, self).split(*args)))

    def rsplit(self, *args):
        return list(map(self.__wrap, super(numbered_line, self).rsplit(*args)))

class LineError(ValueError):

    def __init__(self, msg, line=None):
        super(LineError, self).__init__(context_prefix(line) + msg)
        self.line = line

def context_prefix(line, suffix=': '):
    r = []
    if hasattr(line, 'name'):
        r.append(str(line.name))
    if hasattr(line, 'line_number'):
        r.append(str(line.line_number))
    return ', '.join(r) + (suffix if r else '')

def raise_with_context(line):
    import sys
    exc = sys.exc_info()[1]
    tb = sys.exc_info()[2]
    if isinstance(exc, AssertionError):
        raise type(exc)(context_prefix(line) + str(exc)).with_traceback(tb) from None
    raise

def line_blocks(lines):
    r"""Return an iterator over blocks of lines, where a block is a contiguous
    sequence of non-empty lines delimited by start file or end file or one or
    more blank lines.
    >>> list(line_blocks(['a', 'b', '', 'c', 'd']))
    [['a', 'b'], ['c', 'd']]
    """
    block = []
    for line in lines:
        line = line.rstrip('\n')
        if line:
            if not line.startswith('#'):
                block.append(line)
        elif block:
            yield block
            block = []
    if block:
        yield block

def undent_lines(lines):
    r"""Return an iterator over lines with the 'indent' attribute set to the
    logical indent level, starting at zero.
    >>> lines = map(numbered_line, ['  abc', 'def', ' ghi', '  jkl', '   mno', ' pqr', 'stu'])
    >>> il = list(undent_lines(lines))
    >>> il
    ['abc', 'def', 'ghi', 'jkl', 'mno', 'pqr', 'stu']
    >>> [i.indent for i in il]
    [1, 0, 1, 2, 3, 1, 0]
    >>> lines = map(numbered_line, ['  abc', ' def'])
    >>> list(undent_lines(lines))
    Traceback (most recent call last):
    abo.text.LineError: invalid indent
    """
    indent = []
    for line in lines:
        iline = line.lstrip()
        sp = line[:-len(iline)]
        if not sp:
            indent = []
        elif indent:
            while indent and sp != indent[-1]:
                if indent[-1].startswith(sp):
                    indent.pop()
                elif sp.startswith(indent[-1]):
                    indent.append(sp)
                else:
                    break
            if not (indent and sp == indent[-1]) or (not indent and not sp):
                raise LineError('invalid indent', line=line)
        elif sp:
            indent.append(sp)

        iline.indent = len(indent)
        yield iline
