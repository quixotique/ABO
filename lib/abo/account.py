# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account object.

>>> c = Chart(r'''
... expenses
...   household
...     utilities
...       gas
...       electricity
...       water
...     consumibles
...       food
...     transport
...       car
...       taxi
... income
...     salary
...     rent
...     prizes
... ''')
>>> map(unicode, c.accounts()) #doctest: +NORMALIZE_WHITESPACE
[u':expenses',
 u':expenses:household',
 u':expenses:household:utilities',
 u':expenses:household:utilities:gas',
 u':expenses:household:utilities:electricity',
 u':expenses:household:utilities:water',
 u':expenses:household:consumibles',
 u':expenses:household:consumibles:food',
 u':expenses:household:transport',
 u':expenses:household:transport:car',
 u':expenses:household:transport:taxi',
 u':income',
 u':income:salary',
 u':income:rent',
 u':income:prizes']
"""

import re
import abo.text

_regex_account_name = re.compile(r'^[A-Za-z0-9_]+$')

def parse_account_name(text):
    m = _regex_account_name.match(text)
    if m:
        return m.group(0)
    raise ValueError('invalid account name: %r' % (text,))

class Account(object):

    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent

    def __unicode__(self):
        return (unicode(self.parent) if self.parent else u'') + u':' + unicode(self.name)

    def __str__(self):
        return (str(self.parent) if self.parent else '') + ':' + str(self.name)

    def __repr__(self):
        r = []
        r.append(('name', self.name))
        if self.parent is not None:
            r.append(('parent', self.parent))
        return '%s(%s)' % (type(self).__name__, ', '.join('%s=%r' % i for i in r))

class Chart(object):

    def __init__(self, source_file):
        self.source_file = source_file
        self._accounts = None

    def accounts(self):
        if self._accounts is None:
            self._parse(self.source_file)
        return self._accounts

    def _parse(self, source_file):
        self._accounts = []
        if isinstance(source_file, basestring):
            # To facilitate testing.
            import StringIO
            source_file = StringIO.StringIO(source_file)
            source_file.name = 'StringIO'
        name = getattr(source_file, 'name', str(source_file))
        lines = [line.rstrip('\n') for line in source_file]
        lines = abo.text.decode_lines(lines)
        lines = abo.text.number_lines(lines, name=source_file.name)
        lines = abo.text.undent_lines(lines)
        stack = []
        for line in lines:
            if not line:
                continue
            words = line.split()
            if not words:
                raise abo.text.LineError('missing account name', line=line)
            try:
                name = parse_account_name(words[0])
            except ValueError, e:
                raise abo.text.LineError(e, line=line)
            assert line.indent <= len(stack)
            if line.indent < len(stack):
                stack = stack[:line.indent]
            account = Account(words[0], stack[-1] if stack else None)
            self._accounts.append(account)
            stack.append(account)

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
