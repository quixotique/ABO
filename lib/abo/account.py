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
    >>> a.is_substantial()
    False
    >>> c.is_substantial()
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

    def __init__(self, name=None, label=None, parent=None, atype=None):
        assert parent is None or isinstance(parent, Account)
        assert name or label
        self.name = name
        self.label = label and str(label)
        self.parent = parent
        self.atype = atype
        self.wildchild = False
        self._hash = hash(self.label) ^ hash(self.name) ^ hash(self.parent) ^ hash(self.atype)
        self._childcount = 0
        assert self.name or self.label
        if self.parent:
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

    def make_child(self, name=None, label=None, atype=None):
        return type(self)(name=name, label=label, atype=atype, parent=self)

class Chart(object):

    r"""A Chart is a set of accounts.

    >>> c1 = Chart.from_file(r'''#ABO-Legacy-Accounts
    ... exp "Expenses"
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
    ... inc "Income"
    ...     "Salary"
    ...     rent "Rent"
    ...     prizes "Prizes"
    ... cash_assets asset "Cash assets"
    ...   bank asset:cash "Bank account"
    ...   loose_change asset:cash "Loose change"
    ... ''')
    >>> for a in c1.accounts(): print repr(unicode(a)), repr(a.label), repr(a.atype)
    u':Cash assets' 'cash_assets' AccountType.AssetLiability
    u':Cash assets:Bank account' 'bank' AccountType.AssetLiability
    u':Cash assets:Loose change' 'loose_change' AccountType.AssetLiability
    u':Expenses' 'exp' AccountType.ProfitLoss
    u':Expenses:Household' None AccountType.ProfitLoss
    u':Expenses:Household:Consumibles' None AccountType.ProfitLoss
    u':Expenses:Household:Consumibles:Food' 'food' AccountType.ProfitLoss
    u':Expenses:Household:Transport' None AccountType.ProfitLoss
    u':Expenses:Household:Transport:Car' None AccountType.ProfitLoss
    u':Expenses:Household:Transport:Car:Car rego, insurance, maintenance' 'car' AccountType.ProfitLoss
    u':Expenses:Household:Transport:Car:Petrol for cars' 'petrol' AccountType.ProfitLoss
    u':Expenses:Household:Transport:Taxi journeys' 'taxi' AccountType.ProfitLoss
    u':Expenses:Household:Utilities' None AccountType.ProfitLoss
    u':Expenses:Household:Utilities:Electricity' 'elec' AccountType.ProfitLoss
    u':Expenses:Household:Utilities:Gas' 'gas' AccountType.ProfitLoss
    u':Expenses:Household:Utilities:Water usage' 'water' AccountType.ProfitLoss
    u':Income' 'inc' AccountType.ProfitLoss
    u':Income:Prizes' 'prizes' AccountType.ProfitLoss
    u':Income:Rent' 'rent' AccountType.ProfitLoss
    u':Income:Salary' None AccountType.ProfitLoss

    >>> c1.account('food') in c1.account('exp')
    True
    >>> c1.account('food') in c1.account('inc')
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
    ... Fertile
    ...   Eve
    ...   *
    ...   Adam
    ... Infertile
    ... ''')
    >>> for a in c3.accounts(): print repr(unicode(a)), repr(a.label), repr(a.atype), repr(a.wildchild)
    u':Fertile' None None True
    u':Fertile:Adam' None None False
    u':Fertile:Eve' None None False
    u':Infertile' None None False
    >>> c3.account(u':Fertile')
    Account(name=u'Fertile')
    >>> c3.account(u':Fertile:Somebody')
    Account(name=u'Somebody', parent=Account(name=u'Fertile'))
    >>> c3.account(u':Infertile:Somebody')
    Traceback (most recent call last):
    KeyError: "unknown account u':Infertile:Somebody'"

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
        self._accounts = []
        self._index = {}
        for account in accounts:
            self._add_to_index(account)
        return self

    def _add_account(self, account):
        if account in self._accounts:
            return False
        fullname = unicode(account)
        if fullname in self._index:
            raise ValueError('duplicate account %r' % (fullname,))
        if account.label and account.label in self._index:
            raise ValueError('duplicate account label %r' % (account.label,))
        self._accounts.add(account)
        self._index[fullname] = account
        self._index[account.label] = account
        return True

    def account(self, key):
        try:
            if key in self._index:
                return self._index[key]
            if ':' in key[1:]:
                parentname, childname = key.rsplit(':', 1)
                parent = self._index[parentname]
                fullname = unicode(parent) + ':' + childname
                if fullname in self._index:
                    return self._index[fullname]
                if parent.wildchild:
                    child = parent.make_child(name=childname)
                    self._add_account(child)
                    return child
        except KeyError, e:
            pass
        raise KeyError('unknown account %r' % (key,))

    def accounts(self):
        return sorted(self._accounts, key= lambda a: unicode(a))

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
                    m = self._regex_type.search(line)
                    if m:
                        try:
                            atype = {'AL': AccountType.AssetLiability,
                                    'PL': AccountType.ProfitLoss,
                                    'EQ': AccountType.Equity}[m.group(1)]
                        except KeyError:
                            raise abo.text.LineError('invalid account type %r' % (m.group(1),), line=line)
                        line = line[:m.start(0)] + line[m.end(0):]
                    elif stack:
                        atype = stack[-1].atype
                    name = ' '.join(line.split())
                    if not name and not label:
                        raise abo.text.LineError('missing name or label', line=line)
            assert line.indent == len(stack)
            if name:
                account = Account(name=name, label=label, parent= (stack[-1] if stack else None), atype=atype)
                try:
                    self._add_account(account)
                except ValueError:
                    raise abo.text.LineError('duplicate account %r' % unicode(account), line=line)
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
