# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2014 Andrew Bettison

"""Top-level commands.
"""

import os
import logging
import textwrap
import datetime
from itertools import chain
from collections import defaultdict

import abo.cache
import abo.account
import abo.journal
import abo.period
import abo.transaction
from abo.transaction import sign
import abo.balance
from abo.types import struct
from abo.config import InvalidArg, InvalidOption

def cmd_journal(config, opts):
    chart = get_chart(config, opts)
    range, bf, transactions = filter_period(chart, get_transactions(chart, config, opts), opts)
    dw = 11
    bw = config.balance_column_width()
    aw = max(len(a.short_name()) for a in chart.accounts())
    if config.output_width():
        width = max(50, config.output_width())
        aw = min(15, aw)
        pw = max(1, width - (dw + 2 + 1 + bw + 1 + 2 + 1 + aw))
    else:
        pw = 35
        width = dw + 2 + pw + 1 + bw + 1 + 2 + 1 + aw
    fmt = '%-{dw}.{dw}s  %-{pw}.{pw}s %{bw}s %-2.2s %-.{aw}s'.format(**locals())
    yield 'JOURNAL OF TRANSACTIONS'.center(width)
    yield range_line(range).center(width)
    yield ''
    yield fmt % ('Date', 'Particulars', 'Amount', 'DC', 'Account')
    yield fmt % ('-' * dw, '-' * pw, '-' * bw, '--', '-' * aw)
    def entry_fields(e):
        return (config.format_money(abs(e.amount)), ('db' if e.amount < 0 else 'cr'), chart[e.account].short_name())
    if bf:
        for e in sorted(bf.entries(), key=lambda e: (e.cdate or datetime.date.min, e.amount, e.account)):
            yield fmt % (('',
                'Brought forward' + (' due ' + e.cdate.strftime(r'%-d-%b-%Y') if e.cdate else ''),)
                + entry_fields(e))
    for t in transactions:
        desc = textwrap.wrap(t.description(), width=pw)
        entries = list(t.entries)
        yield fmt % ((t.date.strftime(r'%_d-%b-%Y'), desc.pop(0)) + entry_fields(entries.pop(0)))
        while entries:
            yield fmt % (('', desc.pop(0) if desc else '') + (entry_fields(entries.pop(0)) if entries else ('', '', '')))
        if opts['--wrap']:
            while desc:
                yield fmt % ('', desc.pop(0), '', '', '')
    yield fmt % ('-' * dw, '-' * pw, '-' * bw, '--', '-' * aw)

def cmd_chart(config, opts):
    chart = get_chart(config, opts)
    for account in sorted(fullset(select_accounts(chart, opts))):
        if opts['--verbose']:
            line = [account.full_name()]
        else:
            line = ['\t' * (account.depth() - 1) + account.bare_name()]
        if account.label:
            line.append('[%s]' % (account.label,))
        if account.atype and not (account.parent and account.parent.atype == account.atype):
            line.append('=%s' % (abo.account.atype_to_tag[account.atype]))
        for tag in account.tags:
            line.append('=%s' % (tag,))
        yield ' '.join(line)

def cmd_index(config, opts):
    chart = get_chart(config, opts)
    return sorted(chart.keys())

def cmd_acc(config, opts):
    chart = get_chart(config, opts)
    try:
        accounts = filter_accounts(chart, opts['<PRED>'].lstrip())
    except ValueError as e:
        raise InvalidArg('<PRED>', e)
    logging.debug('accounts = %r' % list(map(str, accounts)))
    common_root_account = abo.account.common_root(accounts)
    logging.debug('common_root_account = %r' % str(common_root_account))
    all_transactions = get_transactions(chart, config, opts)
    range, bf, transactions = filter_period(chart, all_transactions, opts)
    dw = 11
    mw = config.money_column_width()
    bw = config.balance_column_width()
    if config.output_width():
        width = max(50, config.output_width())
        pw = max(1, width - (dw + 2 + 2 * (mw + 1) + 1 + bw))
    else:
        pw = 35
        width = dw + 2 + pw + 2 * (mw + 1) + 1 + bw
    fmt = '%-{dw}.{dw}s  %-{pw}.{pw}s %{mw}s %{mw}s %{bw}s'.format(**locals())
    if not opts['--bare']:
        yield 'STATEMENT OF ACCOUNT'.center(width)
        yield range_line(range).center(width)
        yield ''
    yield fmt % ('Date', 'Particulars', 'Debit', 'Credit', 'Balance')
    yield fmt % ('-' * dw, '-' * pw, '-' * mw, '-' * mw, '-' * bw)
    tally = struct()
    tally.balance = 0
    tally.totdb = 0
    tally.totcr = 0
    if bf:
        def bflines():
            for account in accounts:
                if account.is_substantial() and account.atype is not abo.account.AccountType.ProfitLoss or opts['--bring-forward']:
                    if opts['--control']:
                        amount = bf.cbalance(account)
                        if amount != 0:
                            tally.balance += amount
                            yield fmt % ('', '; '.join(filter(bool, ['Brought forward', account.relative_name(common_root_account)])),
                                    config.format_money(-amount) if amount < 0 else '',
                                    config.format_money(amount) if amount > 0 else '',
                                    config.format_money(tally.balance))
                    else:
                        for e in sorted(bf.entries(), key=lambda e: (e.cdate or datetime.date.min, e.amount, e.account)):
                            if chart[e.account] is account and e.amount != 0:
                                tally.balance += e.amount
                                yield fmt % ('', '; '.join(filter(bool, ['Brought forward',
                                                                        'due ' + e.cdate.strftime(r'%-d-%b-%Y') if e.cdate else '',
                                                                        account.relative_name(common_root_account)])),
                                        config.format_money(-e.amount) if e.amount < 0 else '',
                                        config.format_money(e.amount) if e.amount > 0 else '',
                                        config.format_money(tally.balance))

        lines = list(bflines())
        if not opts['--bare'] or tally.balance != 0:
            for line in lines:
                yield line
    if opts['--control']:
        entries = [e for e in chain(*(t.entries for t in all_transactions)) if chart[e.account] in accounts and (e.cdate or e.transaction.date) in range]
        entries.sort(key=lambda e: e.cdate or e.transaction.date)
    else:
        entries = [e for e in chain(*(t.entries for t in transactions)) if chart[e.account] in accounts]
    for e in entries:
        date = e.cdate if opts['--control'] and e.cdate else e.transaction.edate if opts['--effective'] else e.transaction.date
        tally.balance += e.amount
        if e.amount < 0:
            tally.totdb += e.amount
        elif e.amount > 0:
            tally.totcr += e.amount
        desc = e.description(with_due=not opts['--control'], config=config)
        acc = chart[e.account]
        if acc is not common_root_account:
            rel = []
            for par in chain(reversed(list(acc.parents_not_in_common_with(common_root_account))), (acc,)):
                b = par.bare_name()
                for w in b.split():
                    if w not in desc:
                        rel.append(b)
                        break
            if rel:
                desc = '; '.join(s for s in [':'.join(rel), desc] if s)
        if opts['--control'] or (opts['--effective'] and e.transaction.edate != e.transaction.date):
            desc = config.format_date_short(e.transaction.date, relative_to=date) + ' ' + desc
        desc = textwrap.wrap(desc, width=pw)
        yield fmt % (date.strftime(r'%_d-%b-%Y'),
                desc.pop(0) if desc else '',
                config.format_money(-e.amount) if e.amount < 0 else '',
                config.format_money(e.amount) if e.amount > 0 else '',
                config.format_money(tally.balance))
        if opts['--wrap']:
            while desc:
                yield fmt % ('', desc.pop(0), '', '', '')
    yield fmt % ('-' * dw, '-' * pw, '-' * mw, '-' * mw, '-' * bw)
    yield fmt % ('', 'Totals for period',
            config.format_money(-tally.totdb),
            config.format_money(tally.totcr),
            '')
    yield fmt % ('', 'Balance', '', '', config.format_money(tally.balance))

# TODO refactor filter_display_accounts() as method of Formatter
def filter_display_accounts(accounts, opts):
    accounts = set(accounts) # unroll iterator once only
    if opts['--depth'] is not None:
        accounts = set(a for a in accounts if a.depth() <= int(opts['--depth']))
    if not opts['--subtotals']:
        accounts = leafset(accounts)
    return accounts

class Formatter(object):

    def __init__(self, config, opts, accounts, ncolumns):
        self.config = config
        self.opts = opts # TODO get rid of this, only needed to pass to filter_display_accounts()
        self.opt_bare = bool(opts['--bare'])
        self.opt_fullnames = bool(opts['--fullnames'])
        self.opt_subtotals = bool(opts['--subtotals'])
        self.num_columns = ncolumns
        self.labelwid = max(chain([8], (len(a.label or '') for a in accounts)))
        self.balwid = self.config.balance_column_width()
        if self.opt_fullnames:
            self.accwid = max(chain([10], (len(str(a)) for a in accounts)))
        else:
            self.accwid = max(chain([10], (3 * a.depth() + len(a.bare_name()) for a in accounts)))
            if self.opt_bare:
                self.accwid -= 3
        self.width = (self.balwid + 1) * self.num_columns + self.accwid
        if self.config.output_width() and self.width > self.config.output_width():
            self.accwid = max(10, self.config.output_width() - ((self.balwid + 1) * self.num_columns))
            self.width = self.config.output_width()

    @staticmethod
    def plain(text):
        return text

    @staticmethod
    def strong(text):
        pre = []
        picture = []
        pos = 0
        for c in text:
            if c == '\x08':
                pos -= 1
            else:
                if pos < 0:
                    pre[-pos] = c
                elif pos < len(picture):
                    picture[pos].append(c)
                else:
                    assert pos == len(picture)
                    picture.append([c])
                pos += 1
        for p in picture:
            if p[-1] not in p[:-1]:
                p.append(p[-1])
        return ''.join(chain(reversed(pre), ('\x08'.join(p) for p in picture)))

    def fmt(self, text, columns, label=None, fill=None, text_fill=None, column_fill=None, strong=False):
        decor = self.strong if strong else self.plain
        columns = list(columns)
        columns += [''] * (self.num_columns - len(columns))
        return (    ((label or '').ljust(self.labelwid) if self.opts['--labels'] else '')
                  + text.ljust(self.accwid, text_fill or fill or ' ')[:self.accwid]
                  + ''.join(' ' + ((column_fill or fill or ' ') * (self.balwid - len(c)) + decor(c[-self.balwid:])) for c in columns)
               )

    def rule(self, fill='═'):
        return self.fmt('', [], fill=fill)

    def centre(self, text):
        return text.center(self.width)

    def tree(self, title, accounts, amount_columns, depth=None):
        if depth is not None:
            accounts = set(a for a in accounts if a.depth() <= depth)
        accounts = filter_display_accounts(accounts, self.opts) # TODO refactor filter_display_accounts() as method of Formatter
        subaccounts = parentset(accounts)
        all_accounts = [None] + list(sorted(accounts | subaccounts))
        while all_accounts:
            account = all_accounts.pop(0)
            is_subaccount = account in subaccounts
            if not self.opt_subtotals and self.opt_fullnames and is_subaccount:
                continue
            if account is None:
                if self.opt_bare:
                    continue
                text = 'TOTAL ' + title
            elif self.opt_fullnames:
                text = str(account)
            else:
                def has_sibling(account):
                    if not all_accounts:
                        return False
                    for a in all_accounts:
                        if a.depth() <= account.depth():
                            break
                    return a.depth() == account.depth()
                graph = ['├─╴' if has_sibling(account) else '└─╴']
                for a in account.all_parents():
                    graph.append('│  ' if has_sibling(a) else '   ')
                if self.opt_bare:
                    graph.pop()
                text = ''.join(reversed(graph)) + account.bare_name()
            columns = []
            for acol in amount_columns:
                if (account is None or self.opt_subtotals or not is_subaccount) and account in acol:
                    columns.append(self.config.format_money(acol[account]))
                else:
                    columns.append('')
            yield self.fmt(text + ' ', ((' ' + c if c else '') for c in columns),
                            label= (account and account.label) or '',
                            text_fill= '' if is_subaccount else '.',
                            column_fill= '' if is_subaccount else '.',
                            strong= self.opt_subtotals and not is_subaccount)

def make_sections(section_preds, balances):
    for depth, title, pred in section_preds:
        accounts = set()
        bbalances = []
        for b in balances:
            bb = b.clone()
            bb.set_predicate(pred)
            accounts.update(bb.accounts)
            bbalances.append(bb)
        yield struct(depth=depth, title=title, balances=bbalances, accounts=accounts)

def cmd_profloss(config, opts):
    if opts['--tax']:
        section_preds = (
            (None, 'Taxable Income', (lambda a, m: m > 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (None, 'Deductible Expenses', (lambda a, m: m < 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (0,    'Net Taxable Income', (lambda a, m: 'nd' not in a.tags and 'tax' not in a.tags)),
            (None, 'Tax', (lambda a, m: 'tax' in a.tags)),
            (None, 'Taxable Super', (lambda a, m: m > 0 and 'nd' in a.tags and 'sd' in a.tags and 'tax' not in a.tags)),
            (None, 'Non-Taxable Income', (lambda a, m: m > 0 and 'nd' in a.tags and 'sd' not in a.tags and 'tax' not in a.tags)),
            (0,    'Income After Tax', (lambda a, m: m > 0 or 'nd' not in a.tags or 'tax' in a.tags)),
            (None, 'Expenses', (lambda a, m: m < 0 and 'nd' in a.tags and 'tax' not in a.tags)),
        )
    elif opts['--bare']:
        section_preds = (
            (None, '', (lambda a, m: True)),
        )
    else:
        section_preds = (
            (None, 'Income', (lambda a, m: m > 0)),
            (None, 'Expenses', (lambda a, m: m < 0)),
        )
    ranges = parse_ranges(opts)
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    transactions = get_transactions(chart, config, opts)
    plpred = lambda a: a.atype == abo.account.AccountType.ProfitLoss and a in selected_accounts
    balances = [abo.balance.Balance(transactions, r, chart=chart, acc_pred=plpred, use_edate=opts['--effective']) for r in ranges]
    sections = list(make_sections(section_preds, balances))
    all_accounts = set(chain(*(s.accounts for s in sections)))
    f = Formatter(config, opts, all_accounts, len(balances))
    if not f.opt_bare:
        yield f.centre('PROFIT LOSS STATEMENT')
        yield f.fmt('', (b.date_range.first.strftime(r'%_d-%b-%Y') if b.date_range.first else '' for b in balances))
        yield f.fmt('Account', (b.date_range.last.strftime(r'%_d-%b-%Y') if b.date_range.last else '' for b in balances))
        yield f.rule()
    for section in sections:
        columns = [dict((a, b.balance(a)) for a in chain(section.accounts, [None])) for b in section.balances]
        yield from f.tree(section.title, section.accounts, columns, depth=section.depth)
        if not f.opt_bare:
            yield f.rule()
    if not f.opt_bare:
        yield f.fmt('NET PROFIT/-LOSS', (config.format_money(b.balance(None)) for b in balances))

def cmd_bsheet(config, opts):
    plpred = lambda a: a.atype == abo.account.AccountType.ProfitLoss
    alpred = lambda a: a.atype == abo.account.AccountType.AssetLiability
    eqpred = lambda a: a.atype == abo.account.AccountType.Equity
    section_preds = (
        (None, 'Assets', lambda a, m: alpred(a) and m < 0),
        (None, 'Liabilities', lambda a, m: alpred(a) and m > 0),
        (None, 'Equity', lambda a, m: eqpred(a)),
    )
    chart = get_chart(config, opts)
    retained = chart.get_or_create(name='Retained profits', atype=abo.account.AccountType.Equity)
    selected_accounts = select_accounts(chart, opts)
    all_transactions = get_transactions(chart, config, opts)
    ranges = parse_whens(opts)
    amap = {}
    for a in fullset(selected_accounts):
        parent = a.accrual_parent()
        if parent is None or parent is a:
            parent = a.loan_parent()
        if parent is not None and parent is not a:
            amap[a] = parent
    pred = lambda a: a.atype != abo.account.AccountType.ProfitLoss and a in selected_accounts
    balances = [abo.balance.Balance(all_transactions, r, chart=chart,
                                    acc_pred=pred,
                                    acc_map=lambda a: retained if plpred(a) else amap.get(a, a))
                for r in ranges]
    sections = list(make_sections(section_preds, balances))
    all_accounts = set(chain(*(s.accounts for s in sections)))
    f = Formatter(config, opts, all_accounts, len(balances))
    if not f.opt_bare:
        yield f.centre('BALANCE SHEET')
        yield f.fmt('Account', (b.date_range.last.strftime(r'%_d-%b-%Y') if b.date_range.last else '' for b in balances))
        yield f.rule()
    for section in sections:
        columns = [dict((a, -b.balance(a)) for a in chain(section.accounts, [None])) for b in section.balances]
        yield from f.tree(section.title, section.accounts, columns, depth=section.depth)
        if not f.opt_bare:
            yield f.rule()

def cmd_balance(config, opts):
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    all_transactions = get_transactions(chart, config, opts)
    ranges = parse_whens(opts)
    balances = [abo.balance.Balance(all_transactions, r, chart=chart, acc_pred=lambda a: a in selected_accounts) for r in ranges]
    display_accounts = sorted(filter_display_accounts(chain(*(b.accounts for b in balances)), opts))
    logging.debug('display_accounts = %r' % display_accounts)
    aw = max(chain([10], (len(str(a)) for a in display_accounts)))
    bw = config.balance_column_width()
    width = (bw + 1) * len(balances) + 1 + aw
    if config.output_width() and width > config.output_width():
        aw = max(10, config.output_width() - ((bw + 1) * len(balances) + 1))
    fmt = ('%{bw}s ' * len(balances) + ' %.{aw}s').format(**locals())
    yield 'ACCOUNT BALANCES'.center(width)
    yield ''
    line = []
    for b in balances:
        line.append(b.date_range.last.strftime(r'%_d-%b-%Y'))
    line.append('Account')
    yield fmt % tuple(line)
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))
    for account in display_accounts:
        bals = tuple(b.balance(account) for b in balances)
        if list(filter(bool, bals)) or opts['--all']:
            yield fmt % (tuple(config.format_money(bal) for bal in bals) + (str(account),))
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))

def cmd_due(config, opts):
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    transactions = (t for t in get_transactions(chart, config, opts))
    accounts = defaultdict(lambda: [])
    due_accounts = set()
    for t in transactions:
        for e in t.entries:
            account = chart[e.account]
            if account in selected_accounts:
                if account.is_accrual():
                    account = account.accrual_parent()
                    due_accounts.add(account)
                elif e.cdate:
                    due_accounts.add(account)
                accounts[account].append(e)
    due_all = []
    for account, entries in accounts.items():
        if account in due_accounts:
            entries.sort(key=lambda e: e.cdate or e.transaction.date)
            due = defaultdict(lambda: struct(account=account, entries=[]))
            for e in entries:
                date = e.cdate or when #e.transaction.date
                amount = e.amount
                while amount and due:
                    earliest = sorted(due)[0]
                    if sign(due[earliest].entries[0].amount) == sign(amount):
                        break
                    while abs(amount) >= abs(due[earliest].entries[0].amount):
                        amount += due[earliest].entries.pop(0).amount
                        if not due[earliest].entries:
                            del due[earliest]
                            break
                    if amount and earliest in due:
                        e1 = due[earliest].entries[0]
                        assert abs(amount) < abs(e1.amount)
                        due[earliest].entries[0] = e1.replace(amount= e1.amount + amount)._attach(e1.transaction)
                        amount = 0
                if amount:
                    due[date].entries.append(e.replace(amount= amount)._attach(e.transaction))
            due_all += list(due.items())
    due_all.sort(key=lambda a: (a[0], sum(e.amount for e in a[1].entries)))
    bw = config.money_column_width()
    fmt = '%s %s %{bw}s  %s'.format(**locals())
    for date, due in due_all:
        for e in due.entries:
            assert chart[e.account] in due.account, 'e.account=%r account=%r' % (chart[e.account], due.account)
        balance = sum(e.amount for e in due.entries)
        details = []
        if opts['--detail']:
            t = None
            for e in due.entries:
                if e.transaction is not t:
                    t = e.transaction
                    if t.what:
                        details.append(t.what)
                if e.detail:
                    details.append(e.detail)
        account = str(due.account)
        if opts['--labels'] and due.account.label:
            account += ' [' + due.account.label + ']'
        yield fmt % (date.strftime(r'%a %_d-%b-%Y'),
                     '*' if date < when else '=' if date == when else ' ',
                     config.format_money(balance),
                     '; '.join([account] + details))

def cmd_mako(config, opts):
    import sys
    import os.path
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', 'lib', 'mako'))
    import mako
    from mako.template import Template
    import abo.api
    output = Template(filename=os.path.abspath(opts['<template>'])).render_unicode(
            *opts['<args>'],
            abo= abo.api.API(config, opts),
            m= abo.api.API.money_format_factory(),
            mb= abo.api.API.money_format_factory(symbol=False),
            d= abo.api.API.date_format_factory,
            dn= abo.api.API.date_format_factory('%-d/%-m/%Y'),
            dh= abo.api.API.date_format_factory('%-d-%-b-%Y'),
            df= abo.api.API.date_format_factory('%-d %B %Y'),
            ljust= abo.api.API.ljust_factory,
            rjust= abo.api.API.rjust_factory
        )
    class alist(list):
        pass
    ret = alist([output])
    ret.sep = ''
    return ret

def get_chart(config, opts):
    return abo.cache.chart_cache(config, opts).get()

def get_transactions(chart, config, opts):
    transactions = []
    for cache in abo.cache.transaction_caches(chart, config, opts):
        transactions += cache.transactions()
    if not opts['--projection']:
        transactions = [t for t in transactions if not t.is_projection]
    if opts['--effective']:
        datekey = lambda t: (t.edate, t.date)
    else:
        datekey = lambda t: (t.date, t.edate)
    transactions.sort(key=lambda t: datekey(t) + (t.who or '', t.what or '', -t.amount()))
    if opts['--remove']:
        for text in opts['--remove']:
            try:
                pred = chart.parse_predicate(text)
            except ValueError as e:
                raise InvalidOption('--remove', e)
            transactions = abo.account.remove_account(chart, pred, transactions)
    return transactions

def select_accounts(chart, opts):
    try:
        return filter_accounts(chart, (opts['--select'] or '').lstrip())
    except ValueError as e:
        raise InvalidOption('--select', e)

def filter_accounts(chart, text):
    accounts = set(chart.accounts())
    if text:
        pred = chart.parse_predicate(text)
        accounts = set(filter(pred, accounts))
    return accounts

def fullset(accounts):
    full = set()
    for a in accounts:
        full.update(a.self_and_all_parents())
    return full

def parentset(accounts):
    parents = set()
    for a in accounts:
        parents.update(a.all_parents())
    return parents

def leafset(accounts):
    leaves = set(accounts)
    return leaves.difference(parentset(leaves))

def parse_whens(opts):
    whens = abo.period.parse_whens(opts['<when>']) if opts['<when>'] else [datetime.date.today()]
    return [abo.balance.Range(None, when) for when in whens]

def parse_ranges(opts):
    if opts['<period>']:
        periods = abo.period.parse_periods(opts['<period>'])
    else:
        periods = [(None, None)]
    return [abo.balance.Range(p[0], p[1] if p[1] is not None else datetime.date.today()) for p in periods]

def parse_range(words):
    periods = abo.period.parse_periods(words)
    if len(periods) > 1:
        raise ValueError('too many periods')
    period = periods[0]
    return abo.balance.Range(period[0], period[1])

def filter_period(chart, transactions, opts):
    brought_forward = None
    if opts['<period>']:
        try:
            range = parse_range(opts['<period>'])
        except ValueError as e:
            raise InvalidArg('<period>', e)
        if range.first is not None:
            brought_forward = abo.balance.Balance(transactions, abo.balance.Range(None, range.first - datetime.timedelta(1)), chart=chart, use_edate=opts['--effective'])
        transactions = (t for t in transactions if (t.edate if opts['--effective'] else t.date) in range)
    else:
        range = abo.balance.Range(None, None)
    return range, brought_forward, transactions

def range_line(range):
    p = []
    if range.first is not None:
        p.append('FROM')
        p.append(range.first.strftime(r'%_d-%b-%Y'))
    if range.last is not None:
        p.append('TO')
        p.append(range.last.strftime(r'%_d-%b-%Y'))
    return ' '.join(p) if p else 'ALL DATES'