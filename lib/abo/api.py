# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2014 Andrew Bettison

"""The ABO external application programming interface.
"""

import logging
import datetime
import re
from collections import defaultdict
from itertools import chain
import abo.period
import abo.cache
from abo.text import LineError
import abo.money

class API(object):

    advance_date = staticmethod(abo.period.advance_date)

    @staticmethod
    def money_format(m):
        if isinstance(m, str):
            m = abo.money.Money.from_text(m)
        elif hasattr(m, 'amount') and isinstance(m.date, abo.money.Money):
            m = m.amount
        if not isinstance(m, abo.money.Money):
            raise TypeError('not an abo.money.Money: %r' % (m,))
        return m.format()

    @staticmethod
    def date_format_factory(fmt):
        def formatter(d):
            if isinstance(d, str):
                d = datetime.datetime.strptime(d, '%Y-%m-%d').date()
            elif hasattr(d, 'date') and isinstance(d.date, (datetime.date, datetime.datetime)):
                d = d.date
            if not isinstance(d, (datetime.date, datetime.datetime)):
                raise TypeError('not a date: ' + d)
            return d.strftime(fmt)
        return formatter

    @staticmethod
    def ljust_factory(width, fillchar=' '):
        return lambda s: s.ljust(width, fillchar)

    @staticmethod
    def rjust_factory(width, fillchar=' '):
        return lambda s: s.rjust(width, fillchar)

    def __init__(self, config, opts):
        self.config = config
        self.opts = opts
        self._chart = abo.cache.chart_cache(self.config, self.opts).get()
        self._accounts = dict()
        self.root_account = API_Account(self, None)

    def account(self, account):
        if isinstance(account, str):
            account = self._chart[account]
        assert isinstance(account, abo.account.Account)
        api_account = self._accounts.get(account)
        if api_account is None:
            api_account = API_Account(self, account)
            self._accounts[account] = api_account
        return api_account

    @property
    def all_transactions(self):
        transactions = []
        for cache in abo.cache.transaction_caches(self._chart, self.config, self.opts):
            transactions += cache.transactions()
        transactions.sort(key=lambda t: (t.date, t.who or '', t.what or '', -t.amount()))
        for t in transactions:
            yield API_Transaction(self, t)

class API_Account(object):

    def __init__(self, api, account):
        assert isinstance(api, API)
        assert account is None or isinstance(account, abo.account.Account)
        self._api = api
        self._account = account

    def __str__(self):
        return str(self._account) if self._account is not None else ':'

    def __lt__(self, other):
        if not isinstance(other, API_Account):
            return NotImplemented
        return str(self._account) < str(other._account)

    def __contains__(self, other):
        assert isinstance(other, API_Account)
        return self._account is None or other._account in self._account

    @property
    def entries(self):
        for e in sorted(chain.from_iterable(t.entries for t in self._api.all_transactions), key=lambda e: (e.date, e.amount, e.account, e.description)):
            if e.account in self:
                yield e

    @property
    def movements(self):
        invoice_refs = defaultdict(lambda: [])
        movements = []
        for t in self._api.all_transactions:
            for e in t._trans.entries:
                acc = self._api._chart[e.account]
                if self._account is None or acc in self._account:
                    ref = API_Invoice._extract_ref(e)
                    if ref and acc.is_receivable():
                        invoice_refs[ref].append(e)
                    else:
                        movements.append(API_Movement(API_Entry(self._api, e)))
        for ref in sorted(invoice_refs, key=API_Invoice.ref_sort_key):
            entries = invoice_refs[ref]
            dates = frozenset(e.transaction.date for e in entries)
            if len(dates) != 1:
                raise LineError('invoice %s has inconsistent dates: %s' % (ref, ', '.join(API.format_date(d) for d in sorted(dates))))
            accounts = frozenset(self._api._chart[e.account].accrual_parent() for e in entries)
            if len(accounts) != 1:
                raise LineError('invoice %s has inconsistent accounts: %s' % (ref, ', '.join(str(a) for a in sorted(accounts))))
            account = next(iter(accounts))
            api_account = self if account is self._account else self._api.account(account)
            movements.append(API_Invoice(self._api, ref, api_account, entries))
        for m in sorted(movements, key=lambda e: (e.date, e.amount, e.description)):
            yield m

    @property
    def invoices(self):
        for m in sorted(m for m in self.movements if isinstance(m, API_Invoice)):
            yield m

class API_Invoice(object):

    _re_ref = re.compile(r'\s*\binv:([A-Za-z0-9.-]+)')

    @staticmethod
    def ref_sort_key(text, _re_split = re.compile('(\d+)')):
        return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(_re_split, text))

    @classmethod
    def _extract_refs(cls, entry):
        return frozenset(m.group(1) for m in cls._re_ref.finditer(entry.description()))

    @classmethod
    def _extract_ref(cls, entry):
        refs = cls._extract_refs(entry)
        return next(iter(refs)) if len(refs) == 1 else None

    def __init__(self, api, ref, api_account, entries):
        assert isinstance(api, API)
        assert isinstance(ref, str)
        assert isinstance(api_account, API_Account)
        self._api = api
        self.ref = ref
        self.description = 'Invoice ' + ref
        self.account = api_account
        self._entries = tuple(entries)
        assert len(self._entries) > 0
        self.date = self._entries[0].transaction.date
        self.amount = sum(e.amount for e in self._entries)
        assert self.amount < 0
        invref = 'inv:' + ref
        for e in self._entries:
            assert self._api._chart[e.account] in self.account._account
            assert self._extract_ref(e) == ref
            assert e.transaction.date == self.date, 'e.transaction.date=%r, self.date=%r' % (e.transaction.date, self.date)

    def __lt__(self, other):
        if not isinstance(other, API_Invoice):
            return NotImplemented
        return self.ref_sort_key(self.ref) < self.ref_sort_key(other.ref)

    @property
    def entries(self):
        for e in self._entries:
            desc = '; '.join(part for part in (self._re_ref.sub('', text).strip() for text in (e.transaction.description(), e.detail) if text) if part)
            yield API_Entry(self._api, e, desc=desc)

    def statement(self, since=None):
        return API_Statement(self._api, self.account, since=since, until=self.date)

class API_Movement(object):

    def __init__(self, entry):
        assert isinstance(entry, API_Entry)
        self._api = entry._api
        self.entry = entry
        self.date = entry.date
        self.description = entry.description
        self.amount = entry.amount

class API_Statement(object):

    def __init__(self, api, api_account, since=None, until=None, since_zero_balance=True):
        assert isinstance(api, API)
        assert isinstance(api_account, API_Account)
        if since is not None:
            assert isinstance(since, datetime.date)
        if until is not None:
            assert isinstance(until, datetime.date)
        self._api = api
        self.account = api_account
        self.since = since
        self.until = until
        self.since_zero_balance = since_zero_balance

    @property
    def lines(self):
        balance = 0
        since_zero = []
        for m in self.account.movements:
            if self.until is None or m.date <= self.until:
                balance += m.amount
                if self.since is None or m.date >= self.since:
                    for line in since_zero:
                        yield line
                    since_zero = []
                    yield (m, balance)
                elif self.since_zero_balance:
                    if balance:
                        since_zero.append((m, balance))
                    else:
                        since_zero = []

class API_Transaction(object):

    def __init__(self, api, trans):
        self._api = api
        self._trans = trans
        self.date = trans.date
        self.description = trans.description()

    @property
    def entries(self):
        for e in self._trans.entries:
            assert e.transaction is self._trans
            yield API_Entry(self._api, e, trans=self)

class API_Entry(object):

    def __init__(self, api, entry, trans=None, desc=None):
        self._api = api
        self._entry = entry
        self.transaction = trans if trans is not None else API_Transaction(api, entry.transaction)
        self.account = self._api.account(entry.account)
        self.date = self.transaction.date
        self.amount = entry.amount
        self.description = desc if desc is not None else entry.description()
        self.invoice_ref = API_Invoice._extract_ref(entry)
