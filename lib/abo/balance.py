# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Balance is an immutable object representing the state of a set of accounts
at the end of a range of time.

>>> from abo.transaction import Transaction, Entry
>>> t1 = Transaction(date=1, what="One",
...         entries=({'account':'a1', 'amount':14.56}, {'account':'a2', 'amount':-14.56}))
>>> t2 = Transaction(date=2, edate=5, what="Two",
...         entries=({'account':'a1', 'amount':10.01}, {'account':'a2', 'amount':-10.01}))
>>> t3 = Transaction(date=3, what="Three",
...         entries=({'account':'a1', 'amount':-2.50}, {'account':'a2', 'amount':2.50, 'cdate': 6}))
>>> t4 = Transaction(date=4, what="Four",
...         entries=({'account':'a1', 'amount':100.00}, {'account':'a2', 'amount':-100.00, 'cdate': 5}))

>>> b = Balance([t1, t2, t3, t4], date_range=Range(1, 4))
>>> b.first_date
1
>>> b.last_date
4
>>> b.accounts
('a1', 'a2')
>>> b.balance('a1')
122.07
>>> b.cbalance('a1')
122.07
>>> b.balance('a2')
-122.07
>>> b.cbalance('a2')
-24.57
>>> b.entries() #doctest: +NORMALIZE_WHITESPACE
(Entry(account='a2', amount=-24.57),
 Entry(account='a1', amount=122.07),
 Entry(account='a2', amount=-100.0, cdate=5),
 Entry(account='a2', amount=2.5, cdate=6))

>>> b = Balance([t1, t2, t3, t4], date_range=Range(1, 4), use_edate=True)
>>> b.first_date
1
>>> b.last_date
4
>>> b.accounts
('a1', 'a2')
>>> b.balance('a1')
112.06
>>> b.cbalance('a1')
112.06
>>> b.balance('a2')
-112.06
>>> b.cbalance('a2')
-14.56
>>> b.entries() #doctest: +NORMALIZE_WHITESPACE
(Entry(account='a2', amount=-14.56),
 Entry(account='a1', amount=112.06),
 Entry(account='a2', amount=-100.0, cdate=5),
 Entry(account='a2', amount=2.5, cdate=6))

>>> b = Balance([t1, t2, t3, t4], date_range=Range(1, 4), acc_pred=lambda a: a == 'a1')
>>> b.accounts
('a1',)
>>> b.balance('a1')
122.07
>>> b.entries() #doctest: +NORMALIZE_WHITESPACE
(Entry(account='a1', amount=122.07),)

"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.balance
    doctest.testmod(abo.balance)

from collections import defaultdict
from itertools import chain
from abo.types import struct
import abo.transaction

class Balance(object):

    def __init__(self, transactions, date_range=None, chart=None, acc_pred=None, use_edate=False):
        self.date_range = date_range
        self.first_date = None
        self.last_date = None
        self._raw_balances = defaultdict(lambda: struct(cdate=defaultdict(lambda: 0), total=0))
        if chart:
            for acc in chart.substantial_accounts():
                self._raw_balances[acc].total = 0
        for t in transactions:
            date = t.edate if use_edate else t.date
            if self.date_range is None or date in self.date_range:
                if self.first_date is None or date < self.first_date:
                    self.first_date = date
                if self.last_date is None or date > self.last_date:
                    self.last_date = date
                for e in t.entries:
                    if chart:
                        acc = chart[e.account]
                        assert acc is not None
                        assert acc.is_substantial()
                    else:
                        acc = e.account
                    if acc_pred is None or acc_pred(acc):
                        cdate = None if e.cdate is None or self.date_range is None or e.cdate in self.date_range else e.cdate
                        rb = self._raw_balances[acc]
                        rb.cdate[cdate] += e.amount
                        rb.total += e.amount
        self.pred = lambda a, m: True
        self._balances = None

    def clone(self):
        copy = type(self)([])
        copy.date_range = self.date_range
        copy.first_date = self.first_date
        copy.last_date = self.last_date
        copy.pred = self.pred
        copy._raw_balances = self._raw_balances
        copy._balances = None
        return copy

    def set_predicate(self, pred):
        self.pred = pred
        self._balances = None

    def _tally(self):
        if self._balances is None:
            self._balances = defaultdict(lambda: defaultdict(lambda: 0))
            for account, balance in self._raw_balances.items():
                if self.pred(account, balance.total):
                    for cdate, amount in balance.cdate.items():
                        for acc in chain(iter_lineage(account), [None]):
                            self._balances[acc][cdate] += amount

    @property
    def accounts(self):
        self._tally()
        return tuple(sorted((b for b in self._balances if b is not None)))

    def balance(self, account=None):
        self._tally()
        return sum(self._balances[account].values()) if account in self._balances else 0

    def cbalance(self, account=None):
        self._tally()
        return self._balances[account][None]

    def entries(self):
        self._tally()
        without_cdate = []
        with_cdate = []
        for account, amounts in self._balances.items():
            if account is not None:
                if amounts[None]:
                    without_cdate.append(abo.transaction.Entry(transaction=None, amount=amounts[None], account=account))
                for cdate in sorted(d for d in amounts if d is not None):
                    with_cdate.append(abo.transaction.Entry(transaction=None, amount=amounts[cdate], account=account, cdate=cdate))
        without_cdate.sort(key= lambda e: (e.amount, e.account))
        with_cdate.sort(key= lambda e: (e.cdate, e.amount, e.account))
        return tuple(without_cdate + with_cdate)

def iter_lineage(account):
    while account:
        yield account
        account = getattr(account, 'parent', None)

class Range(object):

    def __init__(self, first, last):
        self.first = first
        self.last = last
        assert self.first is None or self.last is None or self.first <= self.last

    def __contains__(self, item):
        if self.first is not None and item < self.first:
            return False
        if self.last is not None and item > self.last:
            return False
        return True

    _undef = object()

    def replace(self, first=_undef, last=_undef):
        return type(self)(first= self.first if first is self._undef else first,
                          last= self.last if last is self._undef else last)
