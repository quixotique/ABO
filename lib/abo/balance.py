# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Balance is an immutable object representing the state of a set of accounts
at a single point in time.  

>>> from abo.transaction import Transaction, Entry
>>> t1 = Transaction(date=1, what="One",
...         entries=({'account':'a1', 'amount':14.56}, {'account':'a2', 'amount':-14.56}))
>>> t2 = Transaction(date=2, what="Two",
...         entries=({'account':'a1', 'amount':10.01}, {'account':'a2', 'amount':-10.01}))
>>> t3 = Transaction(date=3, what="Three",
...         entries=({'account':'a1', 'amount':-2.50}, {'account':'a2', 'amount':2.50, 'cdate': 6}))
>>> t4 = Transaction(date=4, what="Four",
...         entries=({'account':'a1', 'amount':100.00}, {'account':'a2', 'amount':-100.00, 'cdate': 5}))
>>> b = Balance([t1, t2, t3, t4], date_range=Range(1, 5))
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
(Entry(account='a1', amount=122.07),
 Entry(account='a2', amount=-24.57),
 Entry(account='a2', amount=-100.0, cdate=5),
 Entry(account='a2', amount=2.5, cdate=6))

"""

from collections import defaultdict
import abo.transaction

class Balance(object):

    def __init__(self, transactions, date_range=None):
        self.date_range = date_range
        self.first_date = None
        self.last_date = None
        self._balances = {}
        for t in transactions:
            if self.date_range is None or t.date in self.date_range:
                if self.first_date is None or t.date < self.first_date:
                    self.first_date = t.date
                if self.last_date is None or t.date > self.last_date:
                    self.last_date = t.date
                for e in t.entries:
                    if e.account not in self._balances:
                        self._balances[e.account] = defaultdict(lambda: 0)
                    if e.cdate is None or self.date_range is None or e.cdate in self.date_range:
                        self._balances[e.account][None] += e.amount
                    else:
                        self._balances[e.account][e.cdate] += e.amount
        self.accounts = tuple(sorted(self._balances))

    def balance(self, account):
        return sum(self._balances[account].itervalues())

    def cbalance(self, account):
        return self._balances[account][None]

    def entries(self):
        ret = []
        for account, amounts in self._balances.iteritems():
            for cdate, amount in amounts.iteritems():
                if amount:
                    ret.append(abo.transaction.Entry(transaction=None, amount=amount, account=account, cdate=cdate))
        return tuple(sorted(ret, key=lambda e: (e.cdate, e.account, -e.amount)))

class Range(object):

    def __init__(self, start, end):
        self.start = start
        self.end = end
        assert self.start is None or self.end is None or self.start <= self.end

    def __contains__(self, item):
        if self.start is not None and item < self.start:
            return False
        if self.end is not None and item >= self.end:
            return False
        return True

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
