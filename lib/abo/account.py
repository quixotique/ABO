# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account and Chart objects.
"""

import re
import abo.text
from abo.enum import enum
import abo.cache

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
        self.label = label and str(label)
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

    >>> c = Chart.from_file(r'''
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

    def __init__(self):
        self._accounts = None
        self._labels = None

    @classmethod
    def from_file(cls, source_file):
        self = cls()
        self._parse(source_file)
        return self

    @classmethod
    def from_accounts(cls, accounts):
        accounts = list(accounts)
        labels = dict()
        for account in accounts:
            if account.label:
                if account.label in labels:
                    raise ValueError('duplicate account label %r' % (account.label,))
                labels[account.label] = account
        self = cls()
        self._accounts = accounts
        self._labels = labels
        return self

    def account(self, label):
        if label in self._labels:
            return self._labels[label]
        raise KeyError('invalid account label: %r' % (label,))

    def accounts(self):
        return sorted(self._accounts, key= lambda a: unicode(a))

    _regex_line = re.compile('^(?P<label>' + Account._rxpat_label + ')?\s*(?P<type>\w+)?(?::(?P<qual>\w+))?\s*(?:"(?P<name1>[^"]+)"|“(?P<name2>[^”]+)”)$')

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
            label = m.group('label')
            actype = m.group('type')
            qual = m.group('qual')
            if actype and (actype.startswith('ass') or actype.startswith('lia') or actype.startswith('pay') or actype.startswith('rec')):
                atype = AccountType.Equity if qual == 'equity' else AccountType.AssetLiability
            else:
                atype = AccountType.ProfitLoss
            name = m.group('name1') or m.group('name2')
            assert line.indent <= len(stack)
            if line.indent < len(stack):
                stack = stack[:line.indent]
            account = Account(name=name, label=label, parent= (stack[-1] if stack else None), atype=atype)
            if account in self._accounts:
                raise abo.text.LineError('duplicate account %r' % unicode(account), line=line)
            self._accounts.add(account)
            if account.label:
                if account.label in self._labels:
                    raise abo.text.LineError('duplicate account label %r' % (account.label,), line=line)
                self._labels[account.label] = account
            stack.append(account)

class ChartCache(abo.cache.FileCache):

    def __init__(self, path, chart):
        super(ChartCache, self).__init__(path, lambda: chart.accounts())

    def chart(self, **kwargs):
        accounts = self.get(**kwargs)

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
