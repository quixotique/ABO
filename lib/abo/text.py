# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Text processing utilities.
"""

import locale
import re

_regex_encoding = re.compile(r'coding[=:]\s*([-\w.]+)', re.MULTILINE)

def decode_lines(lines, head=10):
    ur"""Iterate over the given lines, decoding them according to a header in
    the first few lines of the file.
    >>> list(decode_lines(['a', 'b', 'c']))
    [u'a', u'b', u'c']
    >>> list(decode_lines(['100\xb15', 'fileencoding=latin1', 'a', '\xa9 2013'])) \
    ... == [u'100±5', u'fileencoding=latin1', u'a', u'© 2013']
    True
    """
    lineiter = iter(lines)
    firstlines = []
    for line in lineiter:
        firstlines.append(line)
        if len(firstlines) >= head:
            break
    m = _regex_encoding.search('\n'.join(firstlines))
    encoding = m.group(1) if m else locale.getlocale()[1] or 'ascii'
    while firstlines:
        yield firstlines.pop(0).decode(encoding)
    for line in lineiter:
        yield line.decode(encoding)

def number_lines(lines, name=None, start=1):
    '''Iterate over the given lines, transforming them into numbered_line
    objects with name and line_number attributes.  Interpret input lines
    starting with "#line " specially.
    >>> nl = list(number_lines(['a', 'b', '#line 8 bar', 'c'], name='foo'))
    >>> len(nl)
    3
    >>> nl[0]
    u'a'
    >>> nl[0].line_number
    1
    >>> nl[0].name
    'foo'
    >>> nl[2]
    u'c'
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

class numbered_line(unicode):

    r'''Sub-class of unicode which carries extra attributes such as
    'line_number' and 'name', which it preserves where needed.
    >>> i = numbered_line(u'abc ')
    >>> i.line_number = 42
    >>> i.name = 'wah'
    >>> i.rstrip()
    u'abc'
    >>> type(i.rstrip())
    <class '__main__.numbered_line'>
    >>> i.rstrip().line_number
    42
    >>> i.rstrip().name
    'wah'
    >>> i[1]
    u'b'
    >>> i[1].name
    'wah'
    >>> i[2:]
    u'c '
    >>> i[2:].name
    'wah'
    >>> i + u'def'
    u'abc def'
    >>> (i + u'def').name
    'wah'
    >>> u'xxx' + i
    u'xxxabc '
    >>> (u'xxx' + i).name
    'wah'
    '''

    def __new__(cls, arg=''):
        if isinstance(arg, cls):
            return arg
        self = super(numbered_line, cls).__new__(cls, arg)
        if isinstance(arg, cls):
            self.__dict__.update(arg.__dict__)
        return self

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

class LineError(ValueError):

    def __init__(self, msg, line=None):
        super(LineError, self).__init__(self.where(line, suffix=': ') + msg)
        self.line = line

    @classmethod
    def where(cls, line, suffix=''):
        r = []
        if hasattr(line, 'name'):
            r.append(str(line.name))
        if hasattr(line, 'line_number'):
            r.append(str(line.line_number))
        return ', '.join(r) + (suffix if r else '')

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
    [u'abc', u'def', u'ghi', u'jkl', u'mno', u'pqr', u'stu']
    >>> [i.indent for i in il]
    [1, 0, 1, 2, 3, 1, 0]
    >>> lines = map(numbered_line, ['  abc', ' def'])
    >>> list(undent_lines(lines))
    Traceback (most recent call last):
    LineError: invalid indent
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

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
