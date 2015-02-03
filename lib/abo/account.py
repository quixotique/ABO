# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account and Chart objects.
"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.account
    doctest.testmod(abo.account)

import logging
import string
import re
from itertools import chain
import abo.text
from abo.enum import enum
from abo.types import struct
from abo.transaction import sign
import abo.cache

class AccountType(enum('AssetLiability', 'ProfitLoss', 'Equity')):
    pass

tag_to_atype = {
    'AL': AccountType.AssetLiability,
    'PL': AccountType.ProfitLoss,
    'EQ': AccountType.Equity,
}

atype_to_tag = dict(list(zip(list(tag_to_atype.values()), list(tag_to_atype.keys()))))

class AccountKeyError(KeyError):

    def __init__(self, key):
        self.key = key
        KeyError.__init__(self, key)

    def __str__(self):
        return 'unknown account %r' % self.key

class InvalidAccountPredicate(ValueError):

    def __init__(self, pred):
        self.pred = pred
        ValueError.__init__(self, pred)

    def __str__(self):
        return 'invalid account predicate %r' % self.pred

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
    >>> c.bare_name()
    'c'
    >>> c.full_name()
    ':a:b:c'
    >>> d
    Account(label='d', parent=Account(label='a'), atype=AccountType.ProfitLoss)
    >>> c.relative_name(a)
    'b:c'
    >>> c.relative_name(b)
    'c'
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
    set()
    >>> b.tags
    {'x'}
    >>> c.tags == {'x', 'y'}
    True
    >>> e.tags == {'a', 'b'}
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
    rxpat_tag = r'\w+'

    def __init__(self, name=None, label=None, parent=None, atype=None, tags=(), wild=False):
        assert parent is None or isinstance(parent, Account)
        if wild:
            assert name is None
            assert label is None
        else:
            assert name or label
        self.name = name and str(name)
        self.label = label and str(label)
        self.parent = parent
        self.atype = atype
        self.tags = set(map(str, tags))
        self.wild = wild
        self._hash = hash(self.label) ^ hash(self.name) ^ hash(self.parent) ^ hash(self.atype) ^ hash(self.wild)
        self._childcount = 0
        if self.wild:
            assert self.name is None
            assert self.label is None
        else:
            assert self.name or self.label
        if self.parent:
            assert parent.atype is None or self.atype == parent.atype, 'self.atype=%r parent.atype=%r' % (self.atype, parent.atype)
            self.tags |= parent.tags
            self.parent._childcount += 1

    def __str__(self):
        return self.full_name()

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
            and self.atype == other.atype
            and self.wild == other.wild)

    def __ne__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, Account):
            return NotImplemented
        return self.full_name_tuple() < other.full_name_tuple()

    def __contains__(self, account):
        if not isinstance(account, Account):
            return False
        return account == self or account.parent in self

    def is_substantial(self):
        return self._childcount == 0

    def is_receivable(self):
        return self.atype is AccountType.AssetLiability and 'rec' in self.tags

    def is_payable(self):
        return self.atype is AccountType.AssetLiability and 'pay' in self.tags

    def is_accrual(self):
        return self.is_receivable() or self.is_payable()

    def full_name_tuple(self):
        return (self.parent.full_name_tuple() if self.parent else ()) + (self.bare_name(),)

    def full_name(self):
        return ':' + ':'.join(self.full_name_tuple())

    def bare_name(self):
        return '*' if self.wild else str(self.name or self.label)

    def relative_name(self, context_account):
        return ':'.join(a.bare_name() for a in chain(reversed(list(self.parents_not_in_common_with(context_account))), (self,)))

    def short_name(self):
        return min(self.all_full_names(), key=len)

    def depth(self):
        return self.parent.depth() + 1 if self.parent else 1

    def all_parents(self):
        acc = self.parent
        while acc is not None:
            yield acc
            acc = acc.parent

    def self_and_all_parents(self):
        acc = self
        while acc is not None:
            yield acc
            acc = acc.parent

    def parents_not_in_common_with(self, other_account):
        other_line = frozenset(other_account.self_and_all_parents()) if other_account is not None else frozenset()
        for parent in self.all_parents():
            if parent in other_line:
                break
            yield parent

    def accrual_parent(self):
        return None if not self.is_accrual() else self if self.parent is None or not self.parent.is_accrual() else self.parent.accrual_parent()

    def all_full_names(self):
        if self.label:
            yield self.label
        if self.name:
            if self.parent:
                for pname in self.parent.all_full_names():
                    yield pname + ':' + self.name
            else:
                yield ':' + self.name

    def make_child(self, name=None, label=None, atype=None, tags=()):
        return type(self)(name=name, label=label, atype=self.atype, tags=tags, parent=self)

def common_root(accounts):
    r'''
    >>> a = Account(label='a')
    >>> b = Account(label='b', parent=a, tags=['x'])
    >>> c = Account(label='c', parent=b, tags=['y'])
    >>> d = Account(label='d', parent=a, atype=AccountType.ProfitLoss)
    >>> e = Account(label='e', tags=['a', 'b'])
    >>> f = Account(label='f', parent=b)
    >>> common_root([c]).label
    'c'
    >>> common_root([c, d]).label
    'a'
    >>> common_root([b, c]).label
    'b'
    >>> common_root([c, e]) is None
    True
    >>> common_root([c, f]).label
    'b'
    '''
    roots = None
    for account in accounts:
        if roots is None:
            roots = set(account.self_and_all_parents())
        else:
            roots.intersection_update(account.self_and_all_parents())
    if not roots:
        return None
    while len(roots) > 1:
        for account in list(roots):
            roots.difference_update(account.all_parents())
    assert len(roots) == 1
    return roots.pop()

class Chart(object):

    r"""A Chart is a set of accounts.

    >>> c1 = Chart.from_file(r'''#ABO-Legacy-Accounts
    ... exp pl "Expenses"
    ...   "Household"
    ...     "Utilities"
    ...       gas :nd "Gas"
    ...       elec :nd "Electricity"
    ...       water :nd,cons "Water usage"
    ...     :nd,cons "Consumibles"
    ...       food "Food"
    ...     "Transport"
    ...       :nd "Car"
    ...         car "Car rego, insurance, maintenance"
    ...         petrol "Petrol for cars"
    ...       taxi "Taxi journeys"
    ... inc pl "Income"
    ...     :nd "Salary"
    ...     rent :nd "Rent"
    ...     prizes "Prizes"
    ... cash_assets asset "Cash assets"
    ...   bank asset:cash "Bank account"
    ...   loose_change asset:cash "Loose change"
    ... ''')
    >>> for a in c1.accounts(): print(repr(str(a)), repr(a.label), repr(a.atype), repr(tuple(sorted(a.tags))))
    ':Cash assets' 'cash_assets' AccountType.AssetLiability ('AL', 'asset')
    ':Cash assets:Bank account' 'bank' AccountType.AssetLiability ('AL', 'asset', 'cash')
    ':Cash assets:Loose change' 'loose_change' AccountType.AssetLiability ('AL', 'asset', 'cash')
    ':Expenses' 'exp' AccountType.ProfitLoss ('PL',)
    ':Expenses:Household' None AccountType.ProfitLoss ('PL',)
    ':Expenses:Household:Consumibles' None AccountType.ProfitLoss ('PL', 'cons', 'nd')
    ':Expenses:Household:Consumibles:Food' 'food' AccountType.ProfitLoss ('PL', 'cons', 'nd')
    ':Expenses:Household:Transport' None AccountType.ProfitLoss ('PL',)
    ':Expenses:Household:Transport:Car' None AccountType.ProfitLoss ('PL', 'nd')
    ':Expenses:Household:Transport:Car:Petrol for cars' 'petrol' AccountType.ProfitLoss ('PL', 'nd')
    ':Expenses:Household:Transport:Car:rego, insurance, maintenance' 'car' AccountType.ProfitLoss ('PL', 'nd')
    ':Expenses:Household:Transport:Taxi journeys' 'taxi' AccountType.ProfitLoss ('PL',)
    ':Expenses:Household:Utilities' None AccountType.ProfitLoss ('PL',)
    ':Expenses:Household:Utilities:Electricity' 'elec' AccountType.ProfitLoss ('PL', 'nd')
    ':Expenses:Household:Utilities:Gas' 'gas' AccountType.ProfitLoss ('PL', 'nd')
    ':Expenses:Household:Utilities:Water usage' 'water' AccountType.ProfitLoss ('PL', 'cons', 'nd')
    ':Income' 'inc' AccountType.ProfitLoss ('PL',)
    ':Income:Prizes' 'prizes' AccountType.ProfitLoss ('PL',)
    ':Income:Rent' 'rent' AccountType.ProfitLoss ('PL', 'nd')
    ':Income:Salary' None AccountType.ProfitLoss ('PL', 'nd')

    >>> c1.tags()
    ['AL', 'PL', 'asset', 'cash', 'cons', 'nd']

    >>> c1['food'] in c1['exp']
    True
    >>> c1['food'] in c1['inc']
    False

    >>> c2 = Chart.from_file(r'''
    ... Expenses =PL [exp]
    ...   Household
    ...     Utilities =UTIL
    ...       Gas [gas] =energy
    ...       Electricity [elec] =energy
    ...       [water] Water usage =cons
    ...     Consumibles =cons
    ...       Food [food]
    ...     Transport
    ...       Car
    ...         rego, [car] insurance, maintenance
    ...         Petrol for cars [petrol] =energy
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

    >>> p1 = c2.parse_predicate('=AL')
    >>> for a in c2.accounts():
    ...     if p1(a):
    ...         print(str(a))
    :Cash assets
    :Cash assets:Bank account
    :Cash assets:Loose change

    >>> p1 = c2.parse_predicate('=UTIL')
    >>> for a in c2.accounts():
    ...     if p1(a):
    ...         print(str(a))
    :Expenses:Household:Utilities
    :Expenses:Household:Utilities:Electricity
    :Expenses:Household:Utilities:Gas
    :Expenses:Household:Utilities:Water usage

    >>> p1 = c1.parse_predicate('=cons')
    >>> for a in c2.accounts():
    ...     if p1(a):
    ...         print(str(a))
    :Expenses:Household:Consumibles
    :Expenses:Household:Consumibles:Food
    :Expenses:Household:Utilities:Water usage

    >>> p1 = c2.parse_predicate('=energy&!=UTIL')
    >>> for a in c2.accounts():
    ...     if p1(a):
    ...         print(str(a))
    :Expenses:Household:Transport:Car:Petrol for cars

    >>> p1 = c2.parse_predicate('/u')
    >>> for a in c2.accounts():
    ...     if p1(a):
    ...         print(str(a))
    :Cash assets:Bank account
    :Expenses:Household
    :Expenses:Household:Consumibles
    :Expenses:Household:Consumibles:Food
    :Expenses:Household:Transport
    :Expenses:Household:Transport:Car
    :Expenses:Household:Transport:Car:Petrol for cars
    :Expenses:Household:Transport:Car:rego, insurance, maintenance
    :Expenses:Household:Transport:Taxi journeys
    :Expenses:Household:Utilities
    :Expenses:Household:Utilities:Electricity
    :Expenses:Household:Utilities:Gas
    :Expenses:Household:Utilities:Water usage

    >>> p2 = c2.parse_predicate('inc|/oo')
    >>> for a in c2.accounts():
    ...     if p2(a):
    ...         print(str(a))
    :Cash assets:Loose change
    :Expenses:Household:Consumibles:Food
    :Income
    :Income:Prizes
    :Income:Rent
    :Income:Salary

    >>> c2.parse_predicate('nonexistent')
    Traceback (most recent call last):
    abo.account.InvalidAccountPredicate: invalid account predicate 'nonexistent'

    >>> c3 = Chart.from_file(r'''
    ... People
    ...   Eve =a
    ...   * =b
    ...   Adam =c
    ... Things
    ... ''')
    >>> for a in c3.accounts(): print(repr(str(a)), repr(a.label), repr(a.atype))
    ':People' None None
    ':People:Adam' None None
    ':People:Eve' None None
    ':Things' None None
    >>> c3[':People']
    Account(name='People')
    >>> c3[':People:Somebody']
    Account(name='Somebody', parent=Account(name='People'), tags=('b',))
    >>> c3[':Things:Somebody']
    Traceback (most recent call last):
    abo.account.AccountKeyError: unknown account ':Things:Somebody'

    """

    def __init__(self):
        self._accounts = None
        self._tags = None
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
        self._tags = set()
        self._wild = {}
        self._index = {}
        for account in accounts:
            self._add_account(account)
        return self

    def _add_account(self, account):
        if account.wild:
            if account.parent in self._wild:
                if self._wild[account.parent] != account:
                    raise ValueError('duplicate wild account %r' % (str(account),))
                return False # already added
            self._wild[account.parent] = account
        else:
            if account in self._accounts:
                for name in account.all_full_names():
                    assert self._index.get(name) is account
                return False # already added
            for name in account.all_full_names():
                if name in self._index:
                    raise ValueError('duplicate account %r' % (name,))
            self._accounts.add(account)
            for name in account.all_full_names():
                self._index[name] = account
        self._tags.update(account.tags)
        return True

    def __len__(self):
        return len(self._index)

    def __contains__(self, key):
        try:
            self[key]
            return True
        except AccountKeyError:
            return False

    def __getitem__(self, key):
        assert key, 'key=%r' % (key,)
        try:
            return self._index[key]
        except KeyError as e:
            pass
        try:
            if ':' in key[1:]:
                parentname, childname = key.rsplit(':', 1)
                parent = self._index[parentname]
                wild = self._wild.get(parent)
                if wild is not None:
                    child = parent.make_child(name=childname, atype=wild.atype, tags=wild.tags)
                    self._add_account(child)
                    return child
        except KeyError as e:
            pass
        raise AccountKeyError(key)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except AccountKeyError:
            return default

    def accounts(self):
        return sorted(self._accounts)

    def substantial_accounts(self):
        return sorted(a for a in self._accounts if a.is_substantial())

    def keys(self):
        return self._index.keys()

    def has_wild_account(self):
        return len(self._wild) != 0

    def tags(self):
        return sorted(self._tags)

    def parse_predicate(self, text):
        func, text = self._parse_disjunction(text)
        if text:
            raise InvalidAccountPredicate(text)
        return func

    def _parse_disjunction(self, text):
        func, text = self._parse_conjunction(text)
        if text and text[0] == '|':
            if text[1:]:
                func2, text = self._parse_disjunction(text[1:])
                if text:
                    raise InvalidAccountPredicate(text)
                return (lambda a: func(a) or func2(a)), text
            raise InvalidAccountPredicate(text)
        return func, text

    def _parse_conjunction(self, text):
        func, text = self._parse_condition(text)
        if text and text[0] == '&':
            if text[1:]:
                func2, text = self._parse_conjunction(text[1:])
                if text:
                    raise InvalidAccountPredicate(text)
                return (lambda a: func(a) and func2(a)), text
            raise InvalidAccountPredicate(text)
        return func, text

    _regex_cond_tag = re.compile(Account.rxpat_tag)
    _regex_cond_pattern = re.compile(r'[^|&]+')

    def _parse_condition(self, text):
        if text.startswith('!'):
            func, text = self._parse_condition(text[1:])
            return (lambda a: not func(a)), text
        if text.startswith('='):
            m = self._regex_cond_tag.match(text, 1)
            if m:
                tag = m.group()
                return (lambda a: tag in a.tags), text[m.end():]
        if text.startswith('/'):
            m = self._regex_cond_pattern.match(text, 1)
            if m:
                pattern = m.group().lower()
                return (lambda a: pattern in a.full_name().lower()), text[m.end():]
        m = self._regex_cond_pattern.match(text)
        if m:
            try:
                account = self[m.group()]
                return (lambda a: a in account, text[m.end():])
            except KeyError:
                raise InvalidAccountPredicate(m.group())
        raise InvalidAccountPredicate(text)

    _regex_legacy_line = re.compile(
            r'^(?P<label>' + Account._rxpat_label + r')?'
        +   r'\s*(?P<type>' + Account.rxpat_tag + r')?'
        +   r'(?::(?P<qual>' + Account.rxpat_tag + r'(?:,' + Account.rxpat_tag + r')*))?'
        +   r'\s*(?:"(?P<name1>[^"]+)"|“(?P<name2>[^”]+)”)$')
    _regex_label = re.compile(r'\[(' + Account._rxpat_label + r')]')
    _regex_tag = re.compile(r'\s*=(' + Account.rxpat_tag + ')\s*')

    def _parse(self, source_file):
        self._accounts = set()
        self._tags = set()
        self._index = {}
        self._wild = {}
        if isinstance(source_file, str):
            # To facilitate testing.
            import io
            source_file = io.StringIO(source_file)
            source_file.name = 'StringIO'
        name = getattr(source_file, 'name', str(source_file))
        lines = [line.rstrip('\n') for line in source_file]
        lines = list(lines)
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
            wild = False
            if is_legacy:
                m = self._regex_legacy_line.match(line)
                if not m:
                    raise abo.text.LineError('malformed line', line=line)
                label = m.group('label')
                actype = m.group('type')
                qual = m.group('qual').split(',') if m.group('qual') else []
                if not actype:
                    atype = None
                elif (actype.startswith('ass') or actype.startswith('lia') or actype.startswith('pay') or actype.startswith('rec')):
                    if 'equity' in qual:
                        atype = AccountType.Equity
                    else:
                        atype = AccountType.AssetLiability
                        tags.add(actype)
                elif actype.startswith('pl'):
                    atype = AccountType.ProfitLoss
                else:
                    raise abo.text.LineError('unknown account type %r' % actype, line=line)
                if qual:
                    tags.update(qual)
                name = m.group('name1') or m.group('name2')
                if stack:
                    if atype is None:
                        atype = stack[-1].atype
                    name = self._deduplicate(name, [a.name for a in stack])
                if atype is not None:
                    tags.add(atype_to_tag[atype])
            else:
                label = None
                atype = None
                for m in self._regex_tag.finditer(line):
                    try:
                        atype = tag_to_atype[m.group(1)]
                    except KeyError:
                        pass
                    tags.add(m.group(1))
                    line = (line[:m.start(0)] + ' ' + line[m.end(0):]).strip()
                if atype is None and stack:
                    atype = stack[-1].atype
                if line == '*':
                    wild = True
                else:
                    m = self._regex_label.search(line)
                    if m:
                        label = str(m.group(1))
                        line = line[:m.start(0)] + line[m.end(0):]
                    name = ' '.join(line.split())
                    if not name and not label:
                        raise abo.text.LineError('missing name or label', line=line)
            assert line.indent == len(stack)
            if name or wild:
                parent = stack[-1] if stack else None
                if parent is not None and parent.atype is not None and parent.atype != atype:
                    raise abo.text.LineError('account type (%s) does not match parent (%s)' % (atype_to_tag[atype], atype_to_tag[parent.atype]), line=line)
                account = Account(name=name, label=label, parent=parent, atype=atype, tags=tags, wild=wild)
                try:
                    self._add_account(account)
                except KeyError as e:
                    raise abo.text.LineError(str(e), line=line)
                stack.append(account)

    @staticmethod
    def _deduplicate(name, pnames):
        words = name.split()
        for pname in pnames:
            pwords = pname.split()
            while pwords:
                if len(pwords) < len(words) and words[:len(pwords)] == pwords:
                    words = words[len(pwords):]
                    while words and not words[0].strip(string.punctuation):
                        words.pop(0)
                    break
                pwords.pop(0)
        return ' '.join(words)

class ChartCache(abo.cache.FileCache):

    def __init__(self, path, chart):
        super(ChartCache, self).__init__(path, lambda: chart.accounts())

    def chart(self, **kwargs):
        accounts = self.get(**kwargs)

def remove_account(chart, pred, transactions):
    from itertools import chain
    from collections import defaultdict
    logging.debug("remove")
    queues = defaultdict(list)
    todo = list(transactions)
    done = []
    while todo:
        t = todo.pop(0)
        remove = defaultdict(lambda: struct(amount=0, entries=[]))
        keep = []
        keep_total = 0
        for e in t.entries:
            if pred(chart[e.account]):
                s = sign(e.amount)
                remove[s].amount += e.amount
                remove[s].entries.append(e)
            else:
                keep.append(e)
                keep_total += e.amount
        # If the transaction involves exclusively removed accounts, then remove
        # the entire transaction.
        if not keep:
            continue
        # Cancel removed entries against each other, leaving removable entries
        # with only one sign.
        if remove[1].entries and remove[-1].entries:
            remove_amount = remove[-1].amount + remove[1].amount
            assert remove_amount == -keep_total
            if remove_amount == 0:
                assert keep
                assert keep_total == 0
                done.append(t.replace(entries=keep))
                logging.debug("   done %r" % (done[-1],))
                continue
            else:
                s = sign(remove_amount)
                e1, e2 = abo.transaction._divide_entries(remove[s].entries, -remove[-s].amount)
                assert e1
                assert e2
                assert sum(e.amount for e in e1) == -remove[-s].amount
                assert sum(e.amount for e in e2) == remove_amount
                remove = e2
                t = t.replace(entries= chain(e2 + keep))
        elif remove[1].entries:
            remove_amount = remove[1].amount
            remove = remove[1].entries
        elif remove[-1].entries:
            remove_amount = remove[-1].amount
            remove = remove[-1].entries
        else:
            done.append(t)
            logging.debug("   done %r" % (done[-1],))
            continue
        logging.debug("remove %u entries from t = %s %s" % (len(remove), t.amount(), t.date))
        while remove:
            account = remove[0].account
            entries = [e for e in remove if e.account == account]
            assert entries
            remove = [e for e in remove if e.account != account]
            assert t is not None
            assert entries == [e for e in t.entries if e.account == account]
            amount = sum(e.amount for e in entries)
            assert sign(amount) == sign(remove_amount)
            assert abs(amount) <= abs(remove_amount)
            # If this account is not the only one to be removed from this
            # transaction, then split this transaction into one containing only
            # this account and a remainder containg all the other removable
            # accounts.
            if remove:
                k1, k2 = abo.transaction._divide_entries(keep, -amount)
                assert sum(e.amount for e in k1) == -amount
                assert k2
                tr = t.replace(entries= chain(entries + k1))
                t = t.replace(entries= chain(remove + k2))
            else:
                tr, t = t, None
            assert tr is not None
            queue = queues[account]
            if not queue or sign(queue[0].amount) == sign(amount):
                logging.debug("   enqueue %s" % (account,))
                queue.append(struct(amount=amount, transaction=tr)) # TODO sort by due date
            else:
                while queue and abs(queue[0].amount) <= abs(amount):
                    logging.debug("   amount=%s queue[0].amount=%s" % (amount, queue[0].amount))
                    assert sign(queue[0].amount) != sign(amount)
                    if abs(queue[0].amount) == abs(amount):
                        k1, keep = keep, None
                    else:
                        k1, k2 = abo.transaction._divide_entries(keep, queue[0].amount)
                        assert k1
                        assert k2
                        assert len(k1) <= len(keep)
                        keep = k2
                        keep_total = sum(e.amount for e in keep)
                    assert sum(e.amount for e in k1) == queue[0].amount
                    done.append(tr.replace(entries= [e for e in chain(k1, queue[0].transaction.entries) if e.account != account]))
                    logging.debug("   done %r" % (done[-1],))
                    amount += queue[0].amount
                    e1, e2 = abo.transaction._divide_entries(entries, -queue[0].amount)
                    assert sum(e.amount for e in e1) == -queue[0].amount
                    assert sum(e.amount for e in e2) == amount
                    entries = e2
                    queue.pop(0)
                if amount and queue:
                    assert entries
                    assert keep
                    logging.debug("   amount=%s queue[0].amount=%s" % (amount, queue[0].amount))
                    assert abs(amount) < abs(queue[0].amount)
                    assert sign(amount) != sign(queue[0].amount)
                    assert abs(amount) <= abs(keep_total)
                    if keep_total == -amount:
                        k1, keep = keep, None
                    else:
                        k1, k2 = abo.transaction._divide_entries(keep, -amount)
                        assert k1
                        assert k2
                        assert len(k1) <= len(keep)
                        keep = k2
                    assert sum(e.amount for e in k1) == -amount
                    qa = [e for e in queue[0].transaction.entries if e.account == account]
                    qo = [e for e in queue[0].transaction.entries if e.account != account]
                    assert sum(e.amount for e in qa) == queue[0].amount
                    assert sum(e.amount for e in qo) == -queue[0].amount
                    qa1, qa2 = abo.transaction._divide_entries(qa, -amount)
                    qo1, qo2 = abo.transaction._divide_entries(qo, amount)
                    assert sum(e.amount for e in qa1) == -amount
                    assert sum(e.amount for e in qo1) == amount
                    done.append(tr.replace(entries= list(chain(k1, qo1))))
                    logging.debug("   done %r" % (done[-1],))
                    queue[0].amount += amount
                    queue[0].transaction = tr.replace(entries= list(chain(qa2, qo2)))
    return done
