# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account and Chart objects.
"""

import re
import abo.text
from abo.enum import enum

def parse_account_label(text):
    m = Account._regex_label.match(text)
    if m:
        return m.group(0)
    raise ValueError('invalid account label: %r' % (text,))

class AccountType(enum('AssetLiability', 'ProfitLoss', 'Equity')):
    pass

class Account(object):

    r"""Account objects are related hierarchically with any number of root
    Accounts.

    >>> a = Account(label='a')
    >>> b = Account(label='b', parent=a)
    >>> c = Account(label='c', parent=b)
    >>> d = Account(label='d', parent=a, atype=AccountType.ProfitLoss)
    >>> e = Account(label='e')
    >>> c
    Account(label='c', parent=Account(label='b', parent=Account(label='a')))
    >>> unicode(c)
    u':a:b:c'
    >>> d
    Account(label='d', parent=Account(label='a'), atype=AccountType.ProfitLoss)
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

    _rxpat_label = r'[A-Za-z0-9_]+'
    _regex_label = re.compile('^' + _rxpat_label + '$')

    def __init__(self, name=None, label=None, parent=None, atype=None):
        assert parent is None or isinstance(parent, Account)
        assert name or label
        self.name = name or label
        self.label = label
        self.parent = parent
        self.atype = atype
        self._hash = hash(self.name) ^ hash(self.parent)
        self._children = dict()
        assert self.name

    def __unicode__(self):
        return (unicode(self.parent) if self.parent else u'') + u':' + unicode(self.name)

    def __str__(self):
        return (str(self.parent) if self.parent else '') + ':' + str(self.name)

    def __repr__(self):
        r = []
        if self.label is not None:
            r.append('label=%r' % (self.label,))
        if self.parent is not None:
            r.append('parent=%r' % (self.parent,))
        if self.atype is not None:
            r.append('atype=%r' % (self.atype,))
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
    ... "Expenses"
    ...   "Household"
    ...     "Utilities"
    ...       gas "Gas"
    ...       elec "Electricity"
    ...       water "Water usage"
    ...     "Consumibles"
    ...       food "Food"
    ...     "Transport"
    ...       "Car"
    ...         car "Car rego, insurance, maintenance"
    ...         petrol "Petrol for cars"
    ...       taxi "Taxi journeys"
    ... "Income"
    ...     "Salary"
    ...     rent "Rent"
    ...     prizes "Prizes"
    ... ''')
    >>> map(unicode, c.accounts()) #doctest: +NORMALIZE_WHITESPACE
    [u':Expenses',
     u':Expenses:Household',
     u':Expenses:Household:Consumibles',
     u':Expenses:Household:Consumibles:Food',
     u':Expenses:Household:Transport',
     u':Expenses:Household:Transport:Car',
     u':Expenses:Household:Transport:Car:Car rego, insurance, maintenance',
     u':Expenses:Household:Transport:Car:Petrol for cars',
     u':Expenses:Household:Transport:Taxi journeys',
     u':Expenses:Household:Utilities',
     u':Expenses:Household:Utilities:Electricity',
     u':Expenses:Household:Utilities:Gas',
     u':Expenses:Household:Utilities:Water usage',
     u':Income',
     u':Income:Prizes',
     u':Income:Rent',
     u':Income:Salary']

    """

    def __init__(self, source_file):
        self.source_file = source_file
        self._accounts = None
        self._labels = None

    def accounts(self):
        if self._accounts is None:
            self._parse(self.source_file)
        return sorted(self._accounts, key= lambda a: unicode(a))

    _regex_line = re.compile('^(' + Account._rxpat_label + ')?\s*(?:"([^"]+)"|“([^”]+)”)$')

    def _parse(self, source_file):
        self._accounts = set()
        self._labels = {}
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
            m = self._regex_line.match(line)
            if not m:
                raise abo.text.LineError('malformed line', line=line)
            label = m.group(1)
            name = m.group(2)
            assert line.indent <= len(stack)
            if line.indent < len(stack):
                stack = stack[:line.indent]
            account = Account(name=name, label=label, parent= stack[-1] if stack else None)
            if account in self._accounts:
                raise abo.text.LineError('duplicate account %r' % unicode(account), line=line)
            self._accounts.add(account)
            if account.label:
                if account.label in self._labels:
                    raise abo.text.LineError('duplicate account label %r' % (account.label,), line=line)
                self._labels[account.label] = account
            stack.append(account)

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
