# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2014 Andrew Bettison

"""The ABO external application programming interface.
"""

import logging
import re
from collections import defaultdict
import abo.cache
from abo.text import LineError

class API(object):

    def __init__(self, config, opts):
        self.config = config
        self.opts = opts
        self._chart = abo.cache.chart_cache(self.config, self.opts).get()
        self._accounts = dict()

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
        assert isinstance(account, abo.account.Account)
        self._api = api
        self._account = account

    def __str__(self):
        return str(self._account)

    def __contains__(self, other):
        assert isinstance(other, API_Account)
        return self._account in other._account

    @property
    def entries(self):
        for t in self._api.all_transactions:
            for e in t.entries:
                if e.account in self:
                    yield e

    @property
    def invoices(self):
        refs = defaultdict(lambda: [])
        for t in self._api.all_transactions:
            for e in t._trans.entries:
                ref = API_Invoice._extract_ref(e)
                acc = self._api._chart[e.account]
                if ref and acc in self._account and acc.is_receivable():
                    refs[ref].append(e)
        for ref in sorted(refs, key=API_Invoice.ref_sort_key):
            entries = refs[ref]
            dates = frozenset(e.transaction.date for e in entries)
            if len(dates) != 1:
                raise LineError('invoice %s has inconsistent dates: %s' % (ref, ', '.join(d.strftime('%-d/%-m/%Y') for d in sorted(dates))))
            accounts = frozenset(self._api._chart[e.account].accrual_parent() for e in entries)
            if len(accounts) != 1:
                raise LineError('invoice %s has inconsistent accounts: %s' % (ref, ', '.join(str(a) for a in sorted(accounts))))
            account = next(iter(accounts))
            api_account = self if account is self._account else self._api.account(account)
            yield API_Invoice(self._api, ref, api_account, entries)

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
        self.account = api_account
        self._entries = tuple(entries)
        assert len(self._entries) > 0
        self.date = self._entries[0].transaction.date
        invref = 'inv:' + ref
        for e in self._entries:
            assert self._api._chart[e.account] in self.account._account
            assert self._extract_ref(e) == ref
            assert e.transaction.date == self.date, 'e.transaction.date=%r, self.date=%r' % (e.transaction.date, self.date)

    def __lt__(self, other):
        if not isinstance(other, API_Invoice):
            return NotImplemented
        return self.ref < other.ref

    @property
    def entries(self):
        for e in self._entries:
            desc = '; '.join(part for part in (self._re_ref.sub('', text).strip() for text in (e.transaction.description(), e.detail) if text) if part)
            yield API_Entry(self._api, e, desc=desc)

    @property
    def statement_entries(self):
        for e in self.account.entries:
            yield e

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
