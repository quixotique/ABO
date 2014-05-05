# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2014 Andrew Bettison

"""Top-level commands.
"""

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

class InvalidArg(ValueError):
    pass

def cmd_journal(config, opts):
    chart = get_chart(config, opts)
    range, bf, transactions = filter_period(chart, get_transactions(chart, config, opts), opts)
    dw = 11
    bw = config.balance_column_width()
    aw = max(len(a.shortname()) for a in chart.accounts())
    if config.output_width():
        width = max(50, config.output_width())
        aw = min(15, aw)
        pw = max(1, width - (dw + 2 + 1 + bw + 1 + 2 + 1 + aw))
    else:
        pw = 35
        width = dw + 2 + pw + 1 + bw + 1 + 2 + 1 + aw
    fmt = u'%-{dw}.{dw}s  %-{pw}.{pw}s %{bw}s %-2.2s %-.{aw}s'.format(**locals())
    yield 'JOURNAL OF TRANSACTIONS'.center(width)
    yield range_line(range).center(width)
    yield ''
    yield fmt % ('Date', 'Particulars', 'Amount', 'DC', 'Account')
    yield fmt % ('-' * dw, '-' * pw, '-' * bw, '--', '-' * aw)
    def entry_fields(e):
        return (config.format_money(abs(e.amount)), ('db' if e.amount < 0 else 'cr'), chart[e.account].shortname())
    if bf:
        for e in bf.entries():
            yield fmt % (('',
                'Brought forward' + (' due ' + e.cdate.strftime(ur'%-d-%b-%Y') if e.cdate else ''),)
                + entry_fields(e))
    for t in transactions:
        desc = textwrap.wrap(t.description(), width=pw)
        entries = list(t.entries)
        yield fmt % ((t.date.strftime(ur'%_d-%b-%Y'), desc.pop(0)) + entry_fields(entries.pop(0)))
        while entries:
            yield fmt % (('', desc.pop(0) if desc else u'') + (entry_fields(entries.pop(0)) if entries else ('', '', '')))
        if opts['--wrap']:
            while desc:
                yield fmt % ('', desc.pop(0), '', '', '')
    yield fmt % ('-' * dw, '-' * pw, '-' * bw, '--', '-' * aw)

def cmd_chart(config, opts):
    chart = get_chart(config, opts)
    acc_pred = parse_account_predicate(chart, opts)
    for account in chart.accounts():
        if acc_pred(account):
            line = [unicode(account)]
            if opts['--verbose']:
                if account.label:
                    line.append('[%s]' % (account.label,))
                for tag in account.tags:
                    line.append('=%s' % (tag,))
                #if account.atype and not (account.parent and account.parent.atype == account.atype):
                #    line.append('=%s' % (abo.account.atype_to_tag[account.atype]))
            yield ' '.join(line)

def cmd_index(config, opts):
    chart = get_chart(config, opts)
    return sorted(chart.iterkeys())

def cmd_acc(config, opts):
    chart = get_chart(config, opts)
    account = chart[opts['<account>']]
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
    fmt = u'%-{dw}.{dw}s  %-{pw}.{pw}s %{mw}s %{mw}s %{bw}s'.format(**locals())
    yield 'STATEMENT OF ACCOUNT'.center(width)
    yield range_line(range).center(width)
    yield ''
    yield fmt % ('Date', 'Particulars', 'Debit', 'Credit', 'Balance')
    yield fmt % ('-' * dw, '-' * pw, '-' * mw, '-' * mw, '-' * bw)
    balance = 0
    totdb = 0
    totcr = 0
    if bf and (account.atype is not abo.account.AccountType.ProfitLoss or opts['--bring-forward']):
        if opts['--control']:
            balance += bf.cbalance(account)
            yield fmt % ('', 'Brought forward',
                    config.format_money(-balance) if balance < 0 else '',
                    config.format_money(balance) if balance > 0 else '',
                    config.format_money(balance))
        else:
            for e in bf.entries():
                if chart[e.account] is account:
                    balance += e.amount
                    yield fmt % ('', 'Brought forward' + (' due ' + e.cdate.strftime(ur'%-d-%b-%Y') if e.cdate else ''),
                            config.format_money(-e.amount) if e.amount < 0 else '',
                            config.format_money(e.amount) if e.amount > 0 else '',
                            config.format_money(balance))
    if opts['--control']:
        entries = [e for e in chain(*(t.entries for t in all_transactions)) if chart[e.account] in account and (e.cdate or e.transaction.date) in range]
        entries.sort(key=lambda e: e.cdate or e.transaction.date)
    else:
        entries = [e for e in chain(*(t.entries for t in transactions)) if chart[e.account] in account]
    for e in entries:
        date = e.cdate if opts['--control'] and e.cdate else e.transaction.date
        balance += e.amount
        if e.amount < 0:
            totdb += e.amount
        elif e.amount > 0:
            totcr += e.amount
        desc = e.description()
        if opts['--control']:
            desc = e.transaction.date.strftime(ur'%-d-%b ') + desc
        desc = textwrap.wrap(desc, width=pw)
        yield fmt % (date.strftime(ur'%_d-%b-%Y'),
                desc.pop(0),
                config.format_money(-e.amount) if e.amount < 0 else '',
                config.format_money(e.amount) if e.amount > 0 else '',
                config.format_money(balance))
        if opts['--wrap']:
            while desc:
                yield fmt % ('', desc.pop(0), '', '', '')
    yield fmt % ('-' * dw, '-' * pw, '-' * mw, '-' * mw, '-' * bw)
    yield fmt % ('', 'Totals for period',
            config.format_money(-totdb),
            config.format_money(totcr),
            '')
    yield fmt % ('', 'Balance', '', '', config.format_money(balance))

def cmd_profloss(config, opts):
    periods = parse_periods(opts)
    chart = get_chart(config, opts)
    acc_pred = parse_account_predicate(chart, opts)
    transactions = get_transactions(chart, config, opts)
    sections = []
    all_accounts = set()
    for depth, title, pred in (
            (10, 'Taxable Income', (lambda a, c, m: m > 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (10, 'Deductible Expenses', (lambda a, c, m: m < 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (0,  'Net Taxable Income', (lambda a, c, m: 'nd' not in a.tags and 'tax' not in a.tags)),
            (10, 'Tax', (lambda a, c, m: 'tax' in a.tags)),
            (10, 'Non-Taxable Income', (lambda a, c, m: m > 0 and 'nd' in a.tags and 'tax' not in a.tags)),
            (0,  'Income After Tax', (lambda a, c, m: m > 0 or 'nd' not in a.tags or 'tax' in a.tags)),
            (10, 'Expenses', (lambda a, c, m: m < 0 and 'nd' in a.tags and 'tax' not in a.tags)),
        ):
        bpred = lambda a, c, m: a.atype == abo.account.AccountType.ProfitLoss and (opts['--all'] or m) and acc_pred(a) and pred(a, c, m)
        balances = [abo.balance.Balance(transactions, abo.balance.Range(p[0], p[1]), chart=chart, pred=bpred) for p in periods]
        accounts = set()
        for b in balances:
            accounts.update(b.accounts)
        sections.append(struct(depth=depth, title=title, balances=balances, accounts=accounts))
        all_accounts.update(accounts)
    bw = config.balance_column_width()
    aw = max(chain([10], (len(unicode(a)) for a in all_accounts)))
    width = (bw + 1) * len(balances) +  1 + aw
    if config.output_width() and width > config.output_width():
        aw = max(10, config.output_width() - ((bw + 1) * len(balances) + 1))
    fmt = (u'%{bw}s ' * len(balances) + u' %.{aw}s').format(**locals())
    yield 'PROFIT LOSS STATEMENT'.center(width)
    line = []
    for balance in balances:
        line.append(balance.date_range.first.strftime(ur'%_d-%b-%Y') if balance.date_range.first else '')
    line.append('')
    yield fmt % tuple(line)
    line = []
    for balance in balances:
        line.append(balance.date_range.last.strftime(ur'%_d-%b-%Y') if balance.date_range.last else '')
    line.append('Account')
    yield fmt % tuple(line)
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))
    totals = [0] * len(balances)
    for section in sections:
        for account in chain([None], sorted((a for a in section.accounts if a.depth() <= section.depth), key=unicode)):
            line = []
            for balance in section.balances:
                line.append(config.format_money(balance.balance(account)))
            line.append(unicode(account) if account is not None else section.title)
            yield fmt % tuple(line)
        yield fmt % (('-' * bw,) * len(section.balances) + ('-' * aw,))
        for i, balance in enumerate(section.balances):
            totals[i] += balance.balance()
    line = []
    for tot in totals:
        line.append(config.format_money(tot))
    line.append('NET PROFIT (LOSS)')
    yield fmt % tuple(line)

def cmd_balance(config, opts):
    chart = get_chart(config, opts)
    acc_pred = parse_account_predicate(chart, opts)
    all_transactions = get_transactions(chart, config, opts)
    when, balance, transactions = filter_at(chart, all_transactions, opts, pred=lambda a, c, m: acc_pred(a))
    bw = config.balance_column_width()
    aw = max(len(unicode(a)) for a in chart.accounts())
    width = bw + 2 + aw
    if config.output_width() and width > config.output_width():
        aw = max(10, config.output_width() - (bw + 2))
    fmt = u'%{bw}s  %.{aw}s'.format(**locals())
    yield 'ACCOUNT BALANCES'.center(width)
    yield when.strftime(ur'%_d-%b-%Y').center(width)
    yield ''
    yield fmt % ('Balance', 'Account')
    yield fmt % ('-' * bw, '-' * aw)
    for account in balance.accounts:
        bal = balance.balance(account)
        if bal or opts['--all']:
            yield fmt % (config.format_money(bal), unicode(account))
    yield fmt % ('-' * bw, '-' * aw)

def cmd_due(config, opts):
    chart = get_chart(config, opts)
    acc_pred = parse_account_predicate(chart, opts)
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    transactions = (t for t in get_transactions(chart, config, opts))
    def is_accrual(account):
        return account.atype is abo.account.AccountType.AssetLiability and ('rec' in account.tags or 'pay' in account.tags)
    accounts = defaultdict(lambda: [])
    due_accounts = set()
    for t in transactions:
        for e in t.entries:
            account = chart[e.account]
            if is_accrual(account):
                while account.parent and is_accrual(account.parent):
                    account = account.parent
                due_accounts.add(account)
            elif e.cdate:
                due_accounts.add(account)
            accounts[account].append(e)
    due_all = []
    for account, entries in accounts.iteritems():
        if account in due_accounts:
            entries.sort(key=lambda e: e.cdate or e.transaction.date)
            due = defaultdict(lambda: 0)
            for e in entries:
                date = e.cdate or when #e.transaction.date
                amount = e.amount
                while amount and due:
                    earliest = sorted(due)[0]
                    if sign(due[earliest]) == sign(amount):
                        break
                    if abs(amount) >= abs(due[earliest]):
                        amount += due[earliest]
                        del due[earliest]
                    else:
                        due[earliest] += amount
                        amount = 0
                if amount:
                    due[date] += amount
            for date, amount in due.iteritems():
                due_all.append((date, amount, account))
    due_all.sort()
    bw = config.money_column_width()
    fmt = u'%s %s %{bw}s  %s'.format(**locals())
    for date, balance, account in due_all:
        yield fmt % (date.strftime(ur'%a %_d-%b-%Y'),
                     '*' if date < when else '=' if date == when else ' ',
                     config.format_money(balance),
                     unicode(account))

_chart_cache = None
_transaction_caches = None

def chart_cache(config, opts):
    global _chart_cache
    if _chart_cache is None:
        def compile_chart():
            logging.info("compile %r", config.chart_file_path)
            chart = abo.account.Chart.from_file(file(config.chart_file_path))
            for tc in transaction_caches(chart, config, opts):
                tc.get()
            return chart
        _chart_cache = abo.cache.FileCache(config, config.chart_file_path, compile_chart, config.input_file_paths, force=opts['--force'])
    return _chart_cache

def transaction_caches(chart, config, opts):
    global _transaction_caches
    if _transaction_caches is None:
        _transaction_caches = []
        for path in config.input_file_paths:
            _transaction_caches.append(abo.cache.TransactionCache(config, path, abo.journal.Journal(config, file(path), chart=chart), [config.chart_file_path], force=opts['--force']))
    return _transaction_caches

def get_chart(config, opts):
    return chart_cache(config, opts).get()

def get_transactions(chart, config, opts):
    transactions = []
    for cache in transaction_caches(chart, config, opts):
        transactions += cache.transactions()
    transactions.sort(key=lambda t: (t.date, t.who or '', t.what or '', -t.amount()))
    if opts['--remove']:
        for account in opts['--remove']:
            acc = chart[account]
            transactions = abo.account.remove_account(chart, lambda a: a in acc, transactions)
    return transactions

def parse_account_predicate(chart, opts):
    text = (opts['--select'] or '').lstrip()
    if not text:
        return lambda a: True
    try:
        return chart.parse_predicate(text)
    except abo.account.InvalidAccountPredicate, e:
        raise InvalidArg(e)

def parse_periods(opts):
    brought_forward = None
    if opts['<period>']:
        periods = abo.period.parse_periods(opts['<period>'])
    else:
        periods = [(None, None)]
    return [(p[0], p[1] if p[1] is not None else datetime.date.today()) for p in periods]

def parse_range(words):
    periods = abo.period.parse_periods(words)
    if len(periods) > 1:
        raise ValueError('too many periods')
    period = periods[0]
    return abo.balance.Range(period[0], period[1])

def filter_period(chart, transactions, opts):
    brought_forward = None
    if opts['<period>']:
        range = parse_range(opts['<period>'])
        if range.first is not None:
            brought_forward = abo.balance.Balance(transactions, abo.balance.Range(None, range.first - datetime.timedelta(1)), chart=chart)
        transactions = (t for t in transactions if t.date in range)
    else:
        range = abo.balance.Range(None, None)
    return range, brought_forward, transactions

def filter_at(chart, transactions, opts, pred=None):
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    range = abo.balance.Range(None, when)
    balance = abo.balance.Balance(transactions, range, chart=chart, pred=pred)
    transactions = [t for t in transactions if t.date in range]
    return when, balance, transactions

def range_line(range):
    p = []
    if range.first is not None:
        p.append('FROM')
        p.append(range.first.strftime(ur'%_d-%b-%Y'))
    if range.last is not None:
        p.append('TO')
        p.append(range.last.strftime(ur'%_d-%b-%Y'))
    return ' '.join(p) if p else 'ALL DATES'

