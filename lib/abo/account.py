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

tag_to_atype = {
    'AL': AccountType.AssetLiability,
    'PL': AccountType.ProfitLoss,
    'EQ': AccountType.Equity,
}

atype_to_tag = dict(zip(tag_to_atype.values(), tag_to_atype.keys()))

class Account(object):

    r"""Account objects are related hierarchically with any number of root
    Accounts.

    >>> a = Account(label='a')
    >>> b = Account(label='b', parent=a, tags=['x'])
    >>> c = Account(label='c', parent=b, tags=['y'])
    >>> d = Account(label='d', parent=a, atype=AccountType.ProfitLoss)
    >>> e = Account(label='e', tags=['a', 'b'])
    >>> c
    Account(label='c', parent=Account(label='b', parent=Account(label='a'), tags=('x',)), tags=('x', 'y'))
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
    >>> a.is_substantial()
    False
    >>> c.is_substantial()
    True
    >>> a.atype
    >>> d.atype
    AccountType.ProfitLoss
    >>> a.tags
    set([])
    >>> b.tags
    set(['x'])
    >>> c.tags == set(['x', 'y'])
    True
    >>> e.tags == set(['a', 'b'])
    True

    Account objects can be pickled and unpickled using protocol 2:

    >>> import pickle
    >>> import abo.account
    >>> pickle.loads(pickle.dumps(d, 2))
    Account(label='d', parent=Account(label='a'), atype=AccountType.ProfitLoss)
    >>> pickle.loads(pickle.dumps(d, 2)) == d
    True

    """

    _rxpat_label = r'[A-Za-z0-9_]+'
    _regex_label = re.compile('^' + _rxpat_label + '$')

    def __init__(self, name=None, label=None, parent=None, atype=None, tags=()):
        assert parent is None or isinstance(parent, Account)
        assert name or label
        self.name = name and unicode(name)
        self.label = label and str(label)
        self.parent = parent
        self.atype = atype
        self.tags = set(map(str, tags))
        self.wildchild = False
        self._hash = hash(self.label) ^ hash(self.name) ^ hash(self.parent) ^ hash(self.atype)
        self._childcount = 0
        assert self.name or self.label
        if self.parent:
            assert parent.atype is None or self.atype == parent.atype, 'self.atype=%r parent.atype=%r' % (self.atype, parent.atype)
            self.tags |= parent.tags
            self.parent._childcount += 1

    def __unicode__(self):
        return (unicode(self.parent) if self.parent else u'') + u':' + unicode(self.name or self.label)

    def __str__(self):
        return (str(self.parent) if self.parent else '') + ':' + str(self.name or self.label)

    def __repr__(self):
        r = []
        if self.label is not None:
            r.append('label=%r' % (self.label,))
        if self.name is not None:
            r.append('name=%r' % (self.name,))
        if self.parent is not None:
            r.append('parent=%r' % (self.parent,))
        if self.atype is not None:
            r.append('atype=%r' % (self.atype,))
        if self.tags:
            r.append('tags=%r' % (tuple(sorted(self.tags)),))
        return '%s(%s)' % (type(self).__name__, ', '.join(r))

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return (self.name == other.name
            and self.label == other.label
            and self.parent == other.parent
            and self.atype == other.atype)

    def __ne__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return not self.__eq__(other)

    def __contains__(self, account):
        if not isinstance(account, Account):
            return False
        return account == self or account.parent in self

    def is_substantial(self):
        return self._childcount == 0

    def make_child(self, name=None, label=None, tags=()):
        return type(self)(name=name, label=label, atype=self.atype, tags=tags, parent=self)

    def shortname(self):
        return min(self.all_full_names(), key=len)

    def all_full_names(self):
        if self.label:
            yield self.label
        if self.name:
            if self.parent:
                for pname in self.parent.all_full_names():
                    yield pname + ':' + self.name
            else:
                yield ':' + self.name

class Chart(object):

    r"""A Chart is a set of accounts.

    >>> c1 = Chart.from_file(r'''#ABO-Legacy-Accounts
    ... exp "Expenses"
    ...   "Household"
    ...     :nd "Utilities"
    ...       gas "Gas"
    ...       elec "Electricity"
    ...       water "Water usage"
    ...     :nd "Consumibles"
    ...       food "Food"
    ...     "Transport"
    ...       :nd "Car"
    ...         car "Car rego, insurance, maintenance"
    ...         petrol "Petrol for cars"
    ...       taxi "Taxi journeys"
    ... inc "Income"
    ...     :nd "Salary"
    ...     rent :nd "Rent"
    ...     prizes "Prizes"
    ... cash_assets asset "Cash assets"
    ...   bank asset:cash "Bank account"
    ...   loose_change asset:cash "Loose change"
    ... ''')
    >>> for a in c1.accounts(): print repr(unicode(a)), repr(a.label), repr(a.atype), repr(tuple(a.tags))
    u':Cash assets' 'cash_assets' AccountType.AssetLiability ()
    u':Cash assets:Bank account' 'bank' AccountType.AssetLiability ()
    u':Cash assets:Loose change' 'loose_change' AccountType.AssetLiability ()
    u':Expenses' 'exp' AccountType.ProfitLoss ()
    u':Expenses:Household' None AccountType.ProfitLoss ()
    u':Expenses:Household:Consumibles' None AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Consumibles:Food' 'food' AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Transport' None AccountType.ProfitLoss ()
    u':Expenses:Household:Transport:Car' None AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Transport:Car:Car rego, insurance, maintenance' 'car' AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Transport:Car:Petrol for cars' 'petrol' AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Transport:Taxi journeys' 'taxi' AccountType.ProfitLoss ()
    u':Expenses:Household:Utilities' None AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Utilities:Electricity' 'elec' AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Utilities:Gas' 'gas' AccountType.ProfitLoss ('nd',)
    u':Expenses:Household:Utilities:Water usage' 'water' AccountType.ProfitLoss ('nd',)
    u':Income' 'inc' AccountType.ProfitLoss ()
    u':Income:Prizes' 'prizes' AccountType.ProfitLoss ()
    u':Income:Rent' 'rent' AccountType.ProfitLoss ('nd',)
    u':Income:Salary' None AccountType.ProfitLoss ('nd',)

    >>> c1['food'] in c1['exp']
    True
    >>> c1['food'] in c1['inc']
    False

    >>> c2 = Chart.from_file(r'''
    ... Expenses =PL [exp]
    ...   Household
    ...     Utilities
    ...       Gas [gas]
    ...       Electricity [elec]
    ...       [water] Water usage
    ...     Consumibles
    ...       Food [food]
    ...     Transport
    ...       Car
    ...         Car rego, [car] insurance, maintenance
    ...         Petrol for cars [petrol]
    ...       Taxi journeys [taxi]
    ... Income [inc] =PL
    ...     Salary
    ...     [rent] Rent
    ...     [prizes] Prizes
    ... =AL Cash assets [cash_assets]
    ...   [bank] Bank account
    ...   [loose_change] Loose change
    ... ''')

    >>> c1.accounts() == c2.accounts()
    True

    >>> c3 = Chart.from_file(r'''
    ... People
    ...   Eve
    ...   *
    ...   Adam
    ... Things
    ... ''')
    >>> for a in c3.accounts(): print repr(unicode(a)), repr(a.label), repr(a.atype), repr(a.wildchild)
    u':People' None None True
    u':People:Adam' None None False
    u':People:Eve' None None False
    u':Things' None None False
    >>> c3[u':People']
    Account(name=u'People')
    >>> c3[u':People:Somebody']
    Account(name=u'Somebody', parent=Account(name=u'People'))
    >>> c3[u':Things:Somebody']
    Traceback (most recent call last):
    KeyError: "unknown account u':Things:Somebody'"

    """

    def __init__(self):
        self._accounts = None
        self._index = None

    @classmethod
    def from_file(cls, source_file):
        self = cls()
        self._parse(source_file)
        return self

    @classmethod
    def from_accounts(cls, accounts):
        self = cls()
        self._accounts = set()
        self._index = {}
        for account in accounts:
            self._add_account(account)
        return self

    def _add_account(self, account):
        if account in self._accounts:
            for name in account.all_full_names():
                assert self._index.get(name) is account
            return False
        for name in account.all_full_names():
            if name in self._index:
                raise ValueError('duplicate account %r' % (name,))
        self._accounts.add(account)
        for name in account.all_full_names():
            self._index[name] = account
        return True

    def __len__(self):
        return len(self._index)

    def __getitem__(self, key):
        assert key
        try:
            return self._index[key]
        except KeyError, e:
            pass
        try:
            if ':' in key[1:]:
                parentname, childname = key.rsplit(':', 1)
                parent = self._index[parentname]
                if parent.wildchild:
                    child = parent.make_child(name=childname)
                    self._add_account(child)
                    return child
        except KeyError, e:
            pass
        raise KeyError('unknown account %r' % (key,))

    def accounts(self):
        return sorted(self._accounts, key= lambda a: unicode(a))

    def iterkeys(self):
        return self._index.iterkeys()

    _regex_legacy_line = re.compile(r'^(?P<label>' + Account._rxpat_label + r')?\s*(?P<type>\w+)?(?::(?P<qual>\w+))?\s*(?:"(?P<name1>[^"]+)"|“(?P<name2>[^”]+)”)$')
    _regex_label = re.compile(r'\[(' + Account._rxpat_label + r')]')
    _regex_type = re.compile(r'=(\w+)')

    def _parse(self, source_file):
        self._accounts = set()
        self._index = {}
        if isinstance(source_file, basestring):
            # To facilitate testing.
            import StringIO
            source_file = StringIO.StringIO(source_file)
            source_file.name = 'StringIO'
        name = getattr(source_file, 'name', str(source_file))
        lines = [line.rstrip('\n') for line in source_file]
        lines = list(abo.text.decode_lines(lines))
        is_legacy = '#ABO-Legacy-Accounts' in lines[:5]
        lines = abo.text.number_lines(lines, name=source_file.name)
        lines = abo.text.undent_lines(lines)
        stack = []
        for line in lines:
            if not line or line.startswith('#'):
                continue
            name = None
            if line.indent < len(stack):
                stack = stack[:line.indent]
            tags = set()
            if is_legacy:
                m = self._regex_legacy_line.match(line)
                if not m:
                    raise abo.text.LineError('malformed line', line=line)
                label = m.group('label')
                actype = m.group('type')
                qual = m.group('qual')
                if actype and (actype.startswith('ass') or actype.startswith('lia') or actype.startswith('pay') or actype.startswith('rec')):
                    atype = AccountType.Equity if qual == 'equity' else AccountType.AssetLiability
                else:
                    atype = AccountType.ProfitLoss
                    if qual:
                        tags.add(qual)
                name = m.group('name1') or m.group('name2')
            else:
                label = None
                atype = None
                if line == '*':
                    if not stack:
                        raise abo.text.LineError('wild child must have parent', line=line)
                    stack[-1].wildchild = True
                else:
                    m = self._regex_label.search(line)
                    if m:
                        label = str(m.group(1))
                        line = line[:m.start(0)] + line[m.end(0):]
                    for m in self._regex_type.finditer(line):
                        try:
                            atype = tag_to_atype[m.group(1)]
                        except KeyError:
                            tags.add(m.group(1))
                        line = line[:m.start(0)] + line[m.end(0):]
                    if atype is None and stack:
                        atype = stack[-1].atype
                    name = ' '.join(line.split())
                    if not name and not label:
                        raise abo.text.LineError('missing name or label', line=line)
            assert line.indent == len(stack)
            if name:
                account = Account(name=name, label=label, parent= (stack[-1] if stack else None), atype=atype, tags=tags)
                try:
                    self._add_account(account)
                except KeyError, e:
                    raise abo.text.LineError(unicode(e), line=line)
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
