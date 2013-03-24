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

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
