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
        self._invoices = None
        self._movements = None

    def account(self, account):
        if isinstance(account, str):
            account = self._chart[account]
        assert isinstance(account, abo.account.Account)
        api_account = self._accounts.get(account)
        if api_account is None:
            api_account = API_Account(self, account)
            self._accounts[account] = api_account
        return api_account

    def _compile(self):
        self._invoices = dict()
        self._movements = list()
        invoice_entries = defaultdict(lambda: [])
        for t in self._all_transactions:
            for e in t.entries:
                acc = self._chart[e.account]
                ref = API_Invoice._extract_ref(e)
                if ref and acc.is_receivable():
                    invoice_entries[ref].append(e)
                else:
                    self._movements.append(API_Entry(self, e))
        for ref, entries in invoice_entries.items():
            #dates = frozenset(e.transaction.date for e in entries)
            #if len(dates) != 1:
            #    raise LineError('invoice %s has inconsistent dates: %s' % (ref, ', '.join(API.format_date(d) for d in sorted(dates))))
            accounts = frozenset(self._chart[e.account].accrual_parent() for e in entries)
            if len(accounts) != 1:
                raise LineError('invoice %s has inconsistent accounts: %s' % (ref, ', '.join(str(a) for a in sorted(accounts))))
            account = next(iter(accounts))
            api_account = self.account(account)
            invoice = API_Invoice(self, ref, api_account, entries)
            self._invoices[ref] = invoice
            self._movements.append(invoice)
        self._movements.sort()

    @property
    def all_movements(self):
        if self._movements is None:
            self._compile()
        return iter(self._movements)

    def invoice(self, ref):
        if self._invoices is None:
            self._compile()
        return self._invoices[ref]

    @property
    def all_invoices(self):
        if self._invoices is None:
            self._compile()
        for ref in sorted(self._invoices, key=API_Invoice.ref_sort_key):
            yield self._invoices[ref]

    @property
    def _all_transactions(self):
        transactions = []
        for cache in abo.cache.transaction_caches(self._chart, self.config, self.opts):
            transactions += cache.transactions()
        transactions.sort(key=lambda t: (t.date, t.who or '', t.what or '', -t.amount()))
        return iter(transactions)

class API_Account(object):

    def __init__(self, api, account):
        assert isinstance(api, API)
        assert account is None or isinstance(account, abo.account.Account)
        self._api = api
        self._account = account
        self.bare_name = account.bare_name() if account is not None else None

    def __str__(self):
        return str(self._account) if self._account is not None else ':'

    def __lt__(self, other):
        if not isinstance(other, API_Account):
            return NotImplemented
        return str(self._account) < str(other._account)

    def __contains__(self, other):
        if isinstance(other, abo.account.Account):
            return self._account is None or other in self._account
        if isinstance(getattr(other, '_account', None), abo.account.Account):
            return other._account in self
        if isinstance(getattr(other, 'account', None), API_Account):
            return other.account in self
        if hasattr(other, '_is_in_account'):
            return other._is_in_account(self)
        return False

    @property
    def entries(self):
        entries = [e for e in chain.from_iterable(t.entries for t in self._api._all_transactions) if e in self]
        for e in sorted(entries, key=lambda e: (e.date, e.amount, e.account, e.description)):
            yield API_Entry(self._api, e)

    @property
    def movements(self):
        for m in self._api.all_movements:
            if m in self:
                yield m

    @property
    def invoices(self):
        for i in self._api.all_invoices:
            if i in self:
                yield i

class API_Movement(object):

    def __init__(self, api, date, amount, description):
        assert type(self) is not API_Movement # must be sub-classed
        self._api = api
        self.date = date
        self.amount = amount
        self.description = description

    def __lt__(self, other):
        if not isinstance(other, API_Movement):
            return NotImplemented
        return (self.date, self.amount, self.description) < (other.date, other.amount, other.description)

class API_Invoice(API_Movement):

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
        assert len(entries) > 0
        amount = sum(e.amount for e in entries)
        assert amount < 0
        API_Movement.__init__(self, api= api,
                                    date= sorted(e.transaction.date for e in entries)[-1],
                                    amount= amount,
                                    description= 'Invoice ' + ref)
        self.ref = ref
        self.account = api_account
        self._entries = tuple(entries)
        invref = 'inv:' + ref
        for e in self._entries:
            assert self._api._chart[e.account] in self.account._account
            assert self._extract_ref(e) == ref
            #assert e.transaction.date == self.date, 'e.transaction.date=%r, self.date=%r' % (e.transaction.date, self.date)

    def __lt__(self, other):
        if isinstance(other, API_Invoice):
            return self.ref_sort_key(self.ref) < self.ref_sort_key(other.ref)
        return super(API_Invoice, self).__lt__(other)

    def _is_in_account(self, account):
        assert isinstance(account, API_Account)
        for e in self._entries:
            if e in account:
                return True
        return False

    @property
    def entries(self):
        for e in self._entries:
            desc = '; '.join(part for part in (self._re_ref.sub('', text).strip() for text in (e.transaction.description(), e.detail) if text) if part)
            yield API_Entry(self._api, e, desc=desc)

    @property
    def lines(self):
        balance = 0
        for e in self.entries:
            balance += e.amount
            yield (e, balance)
        assert balance == self.amount

    def statement(self, since=None, atleast=None):
        return API_Statement(self._api, self.account, since=since, until=self.date, atleast=atleast)

class API_Statement(object):

    def __init__(self, api, api_account, since=None, until=None, atleast=None, since_zero_balance=True):
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
        self.atleast = atleast
        self.since_zero_balance = since_zero_balance

    @property
    def lines(self):
        balance = 0
        since_zero = []
        linecount = 0
        for m in self.account.movements:
            if self.until is None or m.date <= self.until:
                balance += m.amount
                if (   (self.since is None and self.atleast is None)
                    or (self.since is not None and m.date >= self.since)
                    or (self.atleast is not None and linecount < self.atleast)
                ):
                    for line in since_zero:
                        linecount += 1
                        yield line
                    since_zero = []
                    linecount += 1
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

class API_Entry(API_Movement):

    def __init__(self, api, entry, trans=None, desc=None):
        if trans is None:
            trans = API_Transaction(api, entry.transaction)
        else:
            assert isinstance(trans, API_Transaction)
        API_Movement.__init__(self, api= api,
                                    date= trans.date,
                                    amount= entry.amount,
                                    description= desc if desc is not None else entry.description())
        self._entry = entry
        self.transaction = trans
        self.account = self._api.account(entry.account)
        self.invoice_ref = API_Invoice._extract_ref(entry)
