# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Balance is an immutable object representing the state of a set of accounts
at the end of a range of time.

>>> from abo.transaction import Transaction, Entry
>>> t1 = Transaction(date=1, what="One",
...         entries=({'account':'a1', 'amount':14.56}, {'account':'a2', 'amount':-14.56}))
>>> t2 = Transaction(date=2, what="Two",
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
(u'a1', u'a2')
>>> b.balance('a1')
122.07
>>> b.cbalance('a1')
122.07
>>> b.balance('a2')
-122.07
>>> b.cbalance('a2')
-24.57
>>> b.entries() #doctest: +NORMALIZE_WHITESPACE
(Entry(account=u'a2', amount=-24.57),
 Entry(account=u'a1', amount=122.07),
 Entry(account=u'a2', amount=-100.0, cdate=5),
 Entry(account=u'a2', amount=2.5, cdate=6))

"""

from collections import defaultdict
from itertools import chain
import abo.transaction

class Balance(object):

    def __init__(self, transactions, date_range=None, chart=None, pred=lambda a, c, m: True):
        self.date_range = date_range
        self.first_date = None
        self.last_date = None
        balances = defaultdict(lambda: defaultdict(lambda: 0))
        for t in transactions:
            if self.date_range is None or t.date in self.date_range:
                if self.first_date is None or t.date < self.first_date:
                    self.first_date = t.date
                if self.last_date is None or t.date > self.last_date:
                    self.last_date = t.date
                for e in t.entries:
                    cdate = None if e.cdate is None or self.date_range is None or e.cdate in self.date_range else e.cdate
                    acc = chart[e.account] if chart else e.account
                    assert acc is not None
                    balances[acc][cdate] += e.amount
        for acc, cdates in balances.items():
            for cdate, amount in cdates.items():
                if not pred(acc, cdate, amount):
                    del cdates[cdate]
            if not cdates:
                del balances[acc]
        self._balances = defaultdict(lambda: defaultdict(lambda: 0))
        for account, cdates in balances.iteritems():
            for cdate, amount in cdates.iteritems():
                for acc in chain(iter_lineage(account), [None]):
                    self._balances[acc][cdate] += amount
        self.accounts = tuple(sorted((b for b in self._balances if b is not None), key=unicode))

    def balance(self, account=None):
        return sum(self._balances[account].itervalues()) if account in self._balances else 0

    def cbalance(self, account=None):
        return self._balances[account][None]

    def entries(self):
        without_cdate = []
        with_cdate = []
        for account, amounts in self._balances.iteritems():
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


def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
