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

    r'''
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
    '''

    def __new__(cls, arg=''):
        self = super(numbered_line, cls).__new__(cls, arg)
        if hasattr(arg, 'line_number'):
            self.line_number = arg.line_number
        if hasattr(arg, 'name'):
            self.name = arg.name
        return self

    def __wrap(self, value):
        obj = type(self)(value)
        if hasattr(self, 'line_number'):
            obj.line_number = self.line_number
        if hasattr(self, 'name'):
            obj.name = self.name
        return obj

    def rstrip(self, chars=None):
        return self.__wrap(super(numbered_line, self).rstrip(chars))

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

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
