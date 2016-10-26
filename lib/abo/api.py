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
    def parse_date(words):
        return abo.period.parse_when(words)

    @staticmethod
    def money_format_factory(**kwargs):
        def formatter(m):
            if isinstance(m, str):
                m = abo.money.Money.from_text(m)
            elif hasattr(m, 'amount') and isinstance(m.amount, abo.money.Money):
                m = m.amount
            if not isinstance(m, abo.money.Money):
                raise TypeError('not an abo.money.Money: %r' % (m,))
            return m.format(**kwargs)
        return formatter

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
        self._members_account = self._chart.get('mem')

    @property
    def all_accounts(self):
        for a in self._chart.accounts():
            yield self.account(a)

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
        self.full_name = account.full_name() if account is not None else None
        self.bare_name = account.bare_name() if account is not None else None

    def __str__(self):
        return str(self._account) if self._account is not None else ':'

    def __lt__(self, other):
        if not isinstance(other, API_Account):
            return NotImplemented
        return str(self._account) < str(other._account)

    def __contains__(self, other):
        if hasattr(other, '_is_in_account'):
            return other._is_in_account(self)
        if isinstance(other, abo.account.Account):
            return self._account is None or other in self._account
        if isinstance(getattr(other, '_account', None), abo.account.Account):
            return other._account in self
        account = getattr(other, 'account', None)
        if isinstance(account, (abo.account.Account, API_Account)):
            return account in self
        if isinstance(account, str) and account in self._api._chart:
            return self._api._chart[account] in self
        return False

    @property
    def _entries_unsorted(self):
        for t in self._api._all_transactions:
            for e in t.entries:
                if e in self:
                    yield e

    @property
    def _entries(self):
        for e in sorted(self._entries_unsorted, key=lambda e: (e.date, e.amount, e.account, e.description)):
            yield e

    def balance_at(self, date):
        balance = 0
        for e in self._entries_unsorted:
            if e.transaction.date <= date:
                balance += e.amount
        return balance

    @property
    def entries(self):
        for e in self._entries:
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

    def statement(self, until=None, since=None, atleast=None, since_zero_balance=False):
        return API_Statement(self._api, self, since=since, until=until, atleast=atleast, since_zero_balance=since_zero_balance)

    @property
    def sub_accounts(self):
        for a in self._api.all_accounts:
            if a._account.parent is self._account:
                yield a

    @property
    def accounts_receivable(self):
        for a in self.sub_accounts:
            if a._account.is_receivable():
                yield a
            else:
                yield from a.all_accounts_receivable

    @property
    def concept(self):
        if self._account.is_receivable():# and self._account.is_substantial():
            if self._api._members_account is not None and self._account in self._api._members_account:
                return 'member'
            return 'customer'
        return None

class API_Movement(object):

    is_invoice = False

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

    is_invoice = True

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
        self._entries = tuple(sorted(entries, key=lambda e: (e.transaction.date, e.cdate or datetime.date.min, e.transaction.description(), e.detail, e.amount)))
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

    def _strip_ref(self, text):
        return self._re_ref.sub('', text).strip()

    @property
    def entries(self):
        for e in self._entries:
            yield API_Entry(self._api, e, text_filter=self._strip_ref)

    @property
    def lines(self):
        balance = 0
        for e in self.entries:
            balance += e.amount
            yield (e, balance)
        assert balance == self.amount

    def statement_pre(self, since=None, atleast=None, exclude_this=False):
        return API_Statement(self._api,
                             self.account,
                             since=since,
                             since_zero_balance=True,
                             until=self.date,
                             atleast=atleast,
                             exclude=(self,) if exclude_this else ())

    def statement_post(self):
        return API_Statement(self._api,
                             self.account,
                             since=self.date + datetime.timedelta(1),
                             with_brought_forward=False)

    @property
    def movements(self):
        # Return one movement for each distinct due date in the invoice.
        entries_by_due_date = defaultdict(lambda: [])
        for e in self._entries:
            entries_by_due_date[e.cdate or self.date].append(e)
        for due_date in sorted(entries_by_due_date):
            entries = entries_by_due_date[due_date]
            amount = sum(e.amount for e in entries)
            if amount:
                desc = []
                invdesc = []
                if self.description:
                    invdesc.append(self.description)
                if due_date != self.date:
                    invdesc.append('due ' + self._api.config.format_date_short(due_date, relative_to=self.date))
                if invdesc:
                    desc.append(' '.join(invdesc))
                groups = defaultdict(lambda: [])
                for e in entries:
                    transdesc = self._strip_ref(e.transaction.description())
                    detail = []
                    account = self._api._chart[e.account]
                    if account is not self.account._account:
                        detail.append(account.relative_name(self.account._account))
                    detail.append(self._strip_ref(e.detail))
                    group = ' '.join(d for d in detail if d)
                    groups[transdesc].append(group)
                for transdesc in sorted(groups):
                    group = groups[transdesc]
                    groupdesc = []
                    if transdesc:
                        groupdesc.append(transdesc)
                    if group:
                        groupdesc.append(', '.join(d for d in group if d))
                    if groupdesc:
                        desc.append(': '.join(d for d in groupdesc if d))
                yield API_InvoiceMovement(api= self._api,
                                          invoice= self,
                                          due_date= due_date,
                                          amount= amount,
                                          description= '; '.join(desc))

class API_InvoiceMovement(API_Movement):

    is_invoice = True

    def __init__(self, api, invoice, due_date, amount, description):
        API_Movement.__init__(self, api= api,
                                    date= invoice.date,
                                    amount= amount,
                                    description= description)
        self.account = invoice.account
        self.invoice = invoice
        self.invoice_ref = invoice.ref
        self.due_date= due_date

class API_Statement(object):

    def __init__(self,
                 api,
                 api_account,
                 since=None,
                 until=None,
                 atleast=None,
                 since_zero_balance=False,
                 with_brought_forward=True,
                 exclude=()):
        assert isinstance(api, API)
        assert isinstance(api_account, API_Account)
        if until is not None:
            assert isinstance(until, datetime.date)
        if since is not None and not isinstance(since, datetime.date):
            assert until is not None
            if not isinstance(since, datetime.timedelta):
                since = datetime.timedelta(days=since)
            since = until - since
        self._api = api
        self._exclude = frozenset(exclude)
        self.account = api_account
        self.since = since
        self.until = until
        self.atleast = atleast
        self.since_zero_balance = since_zero_balance
        self.with_brought_forward = with_brought_forward
        self._movements = []
        for m in self.account.movements:
            if m not in self._exclude and (self.until is None or m.date <= self.until):
                if isinstance(m, API_Invoice):
                    # Unpack invoice into one movement per due date.
                    self._movements += m.movements
                else:
                    self._movements.append(m)
        self.balance = sum(m.amount for m in self._movements)

    def payments_due(self, date):
        due = defaultdict(lambda: 0)
        overdue_date = date - datetime.timedelta(1)
        paid = 0
        for m in self._movements:
            if m.amount < 0:
                due_date = m.due_date
                if due_date is None or due_date <= overdue_date:
                    due_date = overdue_date
                due[due_date] -= m.amount
            else:
                paid += m.amount
        for due_date in sorted(due):
            amount = due[due_date]
            if amount <= paid:
                paid -= amount
            else:
                yield due_date, amount - paid
                paid = 0

    @property
    def movements(self):
        return iter(self._movements)

    @property
    def lines(self):
        movements = reversed(list(self.movements))
        balance = self.balance
        lines = []
        for m in movements:
            if (    (    (self.atleast is not None and len(lines) < self.atleast)
                      or (self.since_zero_balance and balance != 0))
                and (self.since is None or m.date >= self.since)
            ):
                lines.append((m, balance))
                balance -= m.amount
            else:
                break
        if self.with_brought_forward and balance:
            lines.append((None, balance))
        lines.reverse()
        return iter(lines)

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

    def __init__(self, api, entry, trans=None, text_filter=lambda t: t):
        if trans is None:
            trans = API_Transaction(api, entry.transaction)
        else:
            assert isinstance(trans, API_Transaction)
        desc = []
        desc.append(trans.description)
        detail = []
        account = api._chart[entry.account]
        relname = account.accrual_relative_name()
        if relname:
            detail.append(relname)
        if entry.detail:
            detail.append(text_filter(entry.detail))
        desc.append(' '.join(d for d in detail if d))
        API_Movement.__init__(self, api= api,
                                    date= trans.date,
                                    amount= entry.amount,
                                    description= '; '.join(d for d in desc if d))
        self._entry = entry
        self.transaction = trans
        self.account = self._api.account(entry.account)
        self.invoice_ref = API_Invoice._extract_ref(entry)
        self.due_date= entry.cdate
