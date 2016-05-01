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
    if config.heading:
        yield config.heading.center(width)
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
        yield fmt % ((t.date.strftime(r'%_d-%b-%Y'), desc.pop(0) if desc else '') + entry_fields(entries.pop(0)))
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

def cmd_list(config, opts):
    chart = get_chart(config, opts)
    try:
        accounts = filter_accounts(chart, opts['<PRED>'].lstrip())
    except ValueError as e:
        raise InvalidArg('<PRED>', e)
    for account in sorted(accounts):
        if opts['--verbose']:
            yield account.full_name()
        else:
            yield account.short_name()

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
    if opts['--control']:
        entries = [e for e in chain(*(t.entries for t in all_transactions)) if chart[e.account] in accounts and (e.cdate or e.transaction.date) in range]
        entries.sort(key=lambda e: e.cdate or e.transaction.date)
    else:
        entries = [e for e in chain(*(t.entries for t in transactions)) if chart[e.account] in accounts]
    if opts['--omit-empty'] and not entries:
        return
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
        if config.heading:
            yield config.heading.center(width)
        yield 'STATEMENT OF ACCOUNT'.center(width)
        yield range_line(range).center(width)
        if opts['--title']:
            yield opts['--title'].center(width)
        elif common_root_account is not None:
            yield common_root_account.full_name(prefix='', separator=': ').center(width)
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
    for entry in entries:
        date = entry.cdate if opts['--control'] and entry.cdate else entry.transaction.edate if opts['--effective'] else entry.transaction.date
        tally.balance += entry.amount
        if entry.amount < 0:
            tally.totdb += entry.amount
        elif entry.amount > 0:
            tally.totcr += entry.amount
        desc = entry.description(with_due=not opts['--control'], config=config)
        acc = chart[entry.account]
        if not opts['--short'] and acc is not common_root_account:
            rel = []
            for par in chain(reversed(list(acc.parents_not_in_common_with(common_root_account))), (acc,)):
                b = par.bare_name()
                for w in b.split():
                    if w not in desc:
                        rel.append(b)
                        break
            if rel:
                desc = '; '.join(s for s in [':'.join(rel), desc] if s)
        if not desc and len(entry.transaction.entries) == 2:
            oe = [e for e in entry.transaction.entries if e is not entry]
            assert len(oe) == 1
            oe = oe[0]
            desc = chart[oe.account].bare_name()
        if opts['--control'] or (opts['--effective'] and entry.transaction.edate != entry.transaction.date):
            desc = config.format_date_short(entry.transaction.date, relative_to=date) + ' ' + desc
        desc = textwrap.wrap(desc, width=pw)
        yield fmt % (date.strftime(r'%_d-%b-%Y'),
                desc.pop(0) if desc else '',
                config.format_money(-entry.amount) if entry.amount < 0 else '',
                config.format_money(entry.amount) if entry.amount > 0 else '',
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

class Section(object):

    def __init__(self, sign, depth, title, pred):
        self.sign = sign
        self.depth = depth
        self.title = title
        self.pred = pred

def make_sections(sections, balances):
    for section in sections:
        accounts = set()
        bbalances = []
        for b in balances:
            bb = b.clone()
            bb.set_predicate(section.pred)
            accounts.update(bb.accounts)
            bbalances.append(bb)
        section.balances = bbalances
        section.accounts = accounts

def cmd_profloss(config, opts):
    if opts['--tax']:
        sections = (
            Section(1, None, 'Taxable Income', (lambda a, m: m > 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            Section(1, None, 'Deductible Expenses', (lambda a, m: m < 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            Section(1, 0,    'Net Taxable Income', (lambda a, m: 'nd' not in a.tags and 'tax' not in a.tags)),
            Section(1, None, 'Tax', (lambda a, m: 'tax' in a.tags)),
            Section(1, None, 'Taxable Super', (lambda a, m: m > 0 and 'nd' in a.tags and 'sd' in a.tags and 'tax' not in a.tags)),
            Section(1, None, 'Non-Taxable Income', (lambda a, m: m > 0 and 'nd' in a.tags and 'sd' not in a.tags and 'tax' not in a.tags)),
            Section(1, 0,    'Income After Tax', (lambda a, m: m > 0 or 'nd' not in a.tags or 'tax' in a.tags)),
            Section(1, None, 'Expenses', (lambda a, m: m < 0 and 'nd' in a.tags and 'tax' not in a.tags)),
        )
    elif opts['--bare']:
        sections = (
            Section(1, None, '', (lambda a, m: True)),
        )
    else:
        sections = (
            Section(1, None, 'Income', (lambda a, m: m > 0)),
            Section(1, None, 'Expenses', (lambda a, m: m < 0)),
        )
    ranges = parse_ranges(opts)
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    transactions = get_transactions(chart, config, opts)
    plpred = lambda a: a.atype == abo.account.AccountType.ProfitLoss and a in selected_accounts
    balances = [abo.balance.Balance(transactions, date_range=r, chart=chart, acc_pred=plpred, use_edate=opts['--effective']) for r in ranges]
    make_sections(sections, balances)
    all_accounts = set(chain(*(s.accounts for s in sections)))
    f = Formatter(config, opts, all_accounts, len(balances))
    if not f.opt_bare:
        if config.heading:
            yield f.centre(config.heading)
        yield f.centre('PROFIT LOSS STATEMENT')
        yield f.fmt('', (b.date_range.first.strftime(r'%_d-%b-%Y') if b.date_range.first else '' for b in balances))
        yield f.fmt('Account', (b.date_range.last.strftime(r'%_d-%b-%Y') if b.date_range.last else '' for b in balances))
        yield f.rule()
    for section in sections:
        columns = [dict((a, section.sign * b.balance(a)) for a in chain(section.accounts, [None])) for b in section.balances]
        yield from f.tree(section.title, section.accounts, columns, depth=section.depth)
        if not f.opt_bare:
            yield f.rule()
    if not f.opt_bare:
        yield f.fmt('NET PROFIT/-LOSS', (config.format_money(b.balance(None)) for b in balances))

def cmd_bsheet(config, opts):
    plpred = lambda a: a.atype == abo.account.AccountType.ProfitLoss
    alpred = lambda a: a.atype == abo.account.AccountType.AssetLiability
    eqpred = lambda a: a.atype == abo.account.AccountType.Equity
    sections = (
        Section(-1, None, 'Assets', lambda a, m: alpred(a) and m < 0),
        Section(1, None, 'Liabilities', lambda a, m: alpred(a) and m > 0),
        Section(1, None, 'Equity', lambda a, m: eqpred(a)),
    )
    chart = get_chart(config, opts)
    retained = chart.get_or_create(name='Retained profit(-loss)', atype=abo.account.AccountType.Equity)
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
    balances = [abo.balance.Balance(all_transactions, date_range=r, chart=chart,
                                    acc_pred=pred,
                                    acc_map=lambda a: retained if plpred(a) else amap.get(a, a))
                for r in ranges]
    make_sections(sections, balances)
    all_accounts = set(chain(*(s.accounts for s in sections)))
    f = Formatter(config, opts, all_accounts, len(balances))
    if not f.opt_bare:
        if config.heading:
            yield f.centre(config.heading)
        yield f.centre('BALANCE SHEET')
        yield f.fmt('Account', (b.date_range.last.strftime(r'%_d-%b-%Y') if b.date_range.last else '' for b in balances))
        yield f.rule()
    for section in sections:
        columns = [dict((a, section.sign * b.balance(a)) for a in chain(section.accounts, [None])) for b in section.balances]
        yield from f.tree(section.title, section.accounts, columns, depth=section.depth)
        if not f.opt_bare:
            yield f.rule()

def cmd_balance(config, opts):
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    all_transactions = get_transactions(chart, config, opts)
    ranges = parse_whens(opts)
    balances = [abo.balance.Balance(all_transactions, date_range=r, chart=chart, acc_pred=lambda a: a in selected_accounts) for r in ranges]
    if opts['--journal']:
        for b in balances:
            yield ''
            yield b.date_range.last.strftime(r'%-d/%-m/%Y') + ' balance'
            balance_check = 0
            for e in sorted((e for e in b.entries() if chart[e.account].is_substantial()), key=lambda e: (chart[e.account].short_name(), e.cdate or datetime.date.min, e.amount)):
                balance_check += e.amount
                yield (' ' + chart[e.account].short_name()
                           + '  ' + config.format_money(e.amount, symbol=False, thousands=False)
                           + (e.cdate.strftime(r' ; {%-d/%-m/%Y}') if e.cdate is not None else ''))
            assert balance_check == 0, 'balance_check = %s' % balance_check
    else:
        display_accounts = sorted(filter_display_accounts(chain(*(b.accounts for b in balances)), opts))
        logging.debug('display_accounts = %r' % display_accounts)
        aw = max(chain([10], (len(str(a)) for a in display_accounts)))
        bw = config.balance_column_width()
        width = (bw + 1) * len(balances) + 1 + aw
        if config.output_width() and width > config.output_width():
            aw = max(10, config.output_width() - ((bw + 1) * len(balances) + 1))
        fmt = ('%{bw}s ' * len(balances) + ' %.{aw}s').format(**locals())
        if config.heading:
            yield config.heading.center(width)
        yield 'ACCOUNT BALANCES'.center(width)
        yield ''
        line = []
        for b in balances:
            line.append(b.date_range.last.strftime(r'%_d-%b-%Y'))
        line.append('Account')
        yield fmt % tuple(line)
        yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))
        balance_check = defaultdict(lambda: 0)
        for account in display_accounts:
            amts = [b.balance(account) for b in balances]
            if opts['--all'] or list(filter(bool, amts)):
                yield fmt % (tuple(config.format_money(bal) for bal in amts) + (str(account),))
                for b, amt in zip(balances, amts):
                    balance_check[b] += amt
        for b in balances:
            assert balance_check[b] == 0, 'balance_check[%r] = %s' % (b, balance_check[b])

        yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))

def compute_due_accounts(chart, transactions, selected_accounts=None):
    due_accounts = set()
    accounts = defaultdict(lambda: [])
    for t in transactions:
        for e in t.entries:
            account = chart[e.account]
            if not selected_accounts or account in selected_accounts:
                if account.is_accrual():
                    account = account.accrual_parent()
                    due_accounts.add(account)
                elif e.cdate:
                    due_accounts.add(account)
                accounts[account].append(e)
    return dict((account, entries) for account, entries in accounts.items() if account in due_accounts)

def compute_dues(due_accounts, when):
    due_all = []
    for account, entries in due_accounts.items():
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
    return due_all

def cmd_due(config, opts):
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    transactions = (t for t in get_transactions(chart, config, opts))
    due_accounts = compute_due_accounts(chart, transactions, selected_accounts)
    bw = config.money_column_width()
    fmt = '%s %s %{bw}s  %s'.format(**locals())
    for date, due in compute_dues(due_accounts, when):
        if opts['--over'] and date >= datetime.date.today():
            continue
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

def cmd_table(config, opts):
    chart = get_chart(config, opts)
    selected_accounts = select_accounts(chart, opts)
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    transactions = (t for t in get_transactions(chart, config, opts))
    due_accounts = compute_due_accounts(chart, transactions, selected_accounts)
    # Accumulate due amounts into the table
    slot_headings = ['1+ year',    '6+ months',    '3+ months',    '2+ months',    '1+ month',    '< 1 month', 'future']
    slot_whens =    ['1 year ago', '6 months ago', '3 months ago', '2 months ago', '1 month ago', 'today']
    slot_dates = [abo.period.parse_when(when.split()) for when in slot_whens]
    table = defaultdict(lambda: [0] * len(slot_headings))
    totals = [0] * len(slot_headings)
    usedcols = [False] * len(slot_headings)
    accounts = []
    accountset = set()
    for date, due in compute_dues(due_accounts, when):
        if opts['--over'] and date >= datetime.date.today():
            continue
        slot = next((i for i, sdate in enumerate(slot_dates) if date <= sdate), len(slot_dates))
        for e in due.entries:
            assert chart[e.account] in due.account, 'e.account=%r account=%r' % (chart[e.account], due.account)
            table[due.account][slot] += e.amount
            totals[slot] += e.amount
            usedcols[slot] = True
        if due.account not in accountset:
            accounts.append(due.account)
            accountset.add(due.account)
    # Remove empty columns
    slot = 0
    for used in usedcols:
        if not used:
            del slot_headings[slot]
            for account, tablerow in table.items():
                del tablerow[slot]
            del totals[slot]
        else:
            slot += 1
    # Print the table
    bw = config.money_column_width()
    fmt = ('%{bw}s ' * len(slot_headings) + ' %s').format(**locals())
    if not opts['--bare']:
        yield fmt % (tuple(slot_headings) + ('',))
        yield fmt % (('-' * bw,) * len(slot_headings) + ('',))
    for account in accounts:
        name = account.label if opts['--labels'] and account.label else str(account)
        yield fmt % (tuple(config.format_money(amt) if amt else '-  ' for amt in table[account]) + (name,))
    if not opts['--bare']:
        yield fmt % (('-' * bw,) * len(slot_headings) + ('',))
        yield fmt % (tuple(config.format_money(amt) if amt else '-  ' for amt in totals) + ('',))

def cmd_check(config, opts):
    bw = max(8, config.balance_column_width())
    def format_entry(account, cdate=None, amount=None):
        return (    (config.format_money(amount).rjust(bw) if amount is not None else ' ' * bw) + ' '
                  + ('{' + config.format_date_short(cdate, relative_to=t.date) + '}' if cdate is not None else '').ljust(10) + ' '
                  + str(account))
    chart = get_chart(config, opts)
    all_transactions = get_transactions(chart, config, opts)
    for path in config.checkpoint_file_paths:
        for t in abo.journal.Journal(config, config.open(path)).transactions():
            yield 'checkpoint ' + config.format_date_short(t.date)
            date_range = abo.balance.Range(None, t.date)
            balance = abo.balance.Balance(all_transactions, date_range=date_range, chart=chart, use_edate=opts['--effective'])
            be = defaultdict(lambda: dict())
            for e in balance.entries():
                be[chart[e.account]][e.cdate] = e.amount
            ce = defaultdict(lambda: dict())
            for e in t.entries:
                try:
                    ce[chart[e.account]][e.cdate] = e.amount
                except abo.account.AccountKeyError:
                    yield ('   ' + 'no account'.rjust(bw + 3) + ' ' + format_entry(e.account))
            accounts = frozenset(be) | frozenset(ce)
            for acc in sorted(a for a in accounts if a.is_substantial()):
                cdates = frozenset(be[acc]) | frozenset(ce[acc])
                for cdate in sorted(cdates, key=lambda d: datetime.date.min if d is None else d):
                    bea = be[acc]
                    cea = ce[acc]
                    if cdate not in bea:
                        yield ('   ' + 'missing'.rjust(bw + 3) + ' ' + format_entry(acc, cdate, cea[cdate]))
                    elif cdate not in cea:
                        yield ('   ' + 'spurious'.rjust(bw + 3) + ' ' + format_entry(acc, cdate, bea[cdate]))
                    elif bea[cdate] != cea[cdate]:
                        yield ('   ' + config.format_money(bea[cdate]).rjust(bw) + ' != ' + format_entry(acc, cdate, cea[cdate]))

def cmd_mako(config, opts):
    import sys
    import os.path
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', 'lib', 'mako'))
    import mako
    from mako.template import Template
    from mako.lookup import TemplateLookup
    lookup = TemplateLookup(directories= ['.', '/'] + opts['--template-dir'])
    import abo.api
    output = Template(filename=os.path.abspath(opts['<template>']), lookup=lookup).render_unicode(
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
            brought_forward = abo.balance.Balance(transactions, date_range=abo.balance.Range(None, range.first - datetime.timedelta(1)), chart=chart, use_edate=opts['--effective'])
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
