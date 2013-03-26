# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account and Chart objects.
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

    r"""Account objects are related hierarchically with any number of root
    Accounts.

    >>> a = Account('a')
    >>> b = Account('b', parent=a)
    >>> c = Account('c', parent=b)
    >>> d = Account('d', parent=a)
    >>> e = Account('e')
    >>> c
    Account('c', parent=Account('b', parent=Account('a')))
    >>> unicode(c)
    u':a:b:c'
    >>> a in c
    False
    >>> c in a
    True
    >>> c in e
    False
    >>> s = set([a, c, d])
    >>> a in s
    True
    >>> b in s
    False

    """

    def __init__(self, name, parent=None):
        assert name
        assert parent is None or isinstance(parent, Account)
        self.name = name
        self.parent = parent
        self._hash = hash(self.name) ^ hash(self.parent)
        self._children = dict()

    def __unicode__(self):
        return (unicode(self.parent) if self.parent else u'') + u':' + unicode(self.name)

    def __str__(self):
        return (str(self.parent) if self.parent else '') + ':' + str(self.name)

    def __repr__(self):
        r = [repr(self.name)]
        if self.parent is not None:
            r.append('parent=%r' % (self.parent,))
        return '%s(%s)' % (type(self).__name__, ', '.join(r))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return self.name == other.name and self.parent == other.parent

    def __ne__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return not self.__eq__(other)

    def __contains__(self, account):
        if account in self._children:
            return self._children[account]
        return isinstance(account, Account) and (account == self or account.parent in self)

class Chart(object):

    r"""A Chart is a set of accounts.

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
    u':expenses:household:consumibles',
    u':expenses:household:consumibles:food',
    u':expenses:household:transport',
    u':expenses:household:transport:car',
    u':expenses:household:transport:taxi',
    u':expenses:household:utilities',
    u':expenses:household:utilities:electricity',
    u':expenses:household:utilities:gas',
    u':expenses:household:utilities:water',
    u':income',
    u':income:prizes',
    u':income:rent',
    u':income:salary']

    """

    def __init__(self, source_file):
        self.source_file = source_file
        self._accounts = None

    def accounts(self):
        if self._accounts is None:
            self._parse(self.source_file)
        return sorted(self._accounts.itervalues(), key= lambda a: unicode(a))

    def _parse(self, source_file):
        self._accounts = {}
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
            if not line or line.startswith('#'):
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
            fullname = unicode(account)
            if fullname in self._accounts:
                raise abo.text.LineError('duplicate account name', line=line)
            self._accounts[fullname] = account
            stack.append(account)

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
