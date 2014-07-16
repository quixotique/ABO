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
    acc_pred = parse_option_select_account_predicate(chart, opts)
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
    acc_pred = parse_account_predicate(chart, opts['<PRED>'].lstrip())
    accounts = set(a for a in chart.accounts() if acc_pred(a))
    logging.debug('accounts = %r' % map(unicode, accounts))
    common_root_account = abo.account.common_root(accounts)
    logging.debug('common_root_account = %r' % unicode(common_root_account))
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
    if bf:
        for account in accounts:
            if account.is_substantial() and account.atype is not abo.account.AccountType.ProfitLoss or opts['--bring-forward']:
                if opts['--control']:
                    amount = bf.cbalance(account)
                    if amount != 0:
                        balance += amount
                        yield fmt % ('', '; '.join(filter(bool, ['Brought forward', account.relative_name(common_root_account)])),
                                config.format_money(-amount) if amount < 0 else '',
                                config.format_money(amount) if amount > 0 else '',
                                config.format_money(balance))
                else:
                    for e in bf.entries():
                        if chart[e.account] is account and e.amount != 0:
                            balance += e.amount
                            yield fmt % ('', '; '.join(filter(bool, ['Brought forward',
                                                                     'due ' + e.cdate.strftime(ur'%-d-%b-%Y') if e.cdate else '',
                                                                     account.relative_name(common_root_account)])),
                                    config.format_money(-e.amount) if e.amount < 0 else '',
                                    config.format_money(e.amount) if e.amount > 0 else '',
                                    config.format_money(balance))
    if opts['--control']:
        entries = [e for e in chain(*(t.entries for t in all_transactions)) if chart[e.account] in accounts and (e.cdate or e.transaction.date) in range]
        entries.sort(key=lambda e: e.cdate or e.transaction.date)
    else:
        entries = [e for e in chain(*(t.entries for t in transactions)) if chart[e.account] in accounts]
    for e in entries:
        date = e.cdate if opts['--control'] and e.cdate else e.transaction.date
        balance += e.amount
        if e.amount < 0:
            totdb += e.amount
        elif e.amount > 0:
            totcr += e.amount
        desc = e.description()
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
                desc += '; ' + u':'.join(rel)
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
    acc_pred = parse_option_select_account_predicate(chart, opts)
    transactions = get_transactions(chart, config, opts)
    plpred = lambda a: a.atype == abo.account.AccountType.ProfitLoss and acc_pred(a)
    balances = [abo.balance.Balance(transactions, abo.balance.Range(p[0], p[1]), chart=chart, acc_pred=plpred) for p in periods]
    all_accounts = set()
    if opts['--tax']:
        section_preds = (
            (10, 'Taxable Income', (lambda a, m: m > 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (10, 'Deductible Expenses', (lambda a, m: m < 0 and 'nd' not in a.tags and 'tax' not in a.tags)),
            (0,  'Net Taxable Income', (lambda a, m: 'nd' not in a.tags and 'tax' not in a.tags)),
            (10, 'Tax', (lambda a, m: 'tax' in a.tags)),
            (10, 'Non-Taxable Income', (lambda a, m: m > 0 and 'nd' in a.tags and 'tax' not in a.tags)),
            (0,  'Income After Tax', (lambda a, m: m > 0 or 'nd' not in a.tags or 'tax' in a.tags)),
            (10, 'Expenses', (lambda a, m: m < 0 and 'nd' in a.tags and 'tax' not in a.tags)),
        )
    else:
        section_preds = (
            (10, 'Income', (lambda a, m: m > 0)),
            (10, 'Expenses', (lambda a, m: m < 0)),
        )
    sections = []
    for depth, title, pred in section_preds:
        accounts = set()
        bbalances = []
        for b in balances:
            bb = b.clone()
            bb.set_predicate(pred)
            accounts.update(bb.accounts)
            bbalances.append(bb)
        sections.append(struct(depth=depth, title=title, balances=bbalances, accounts=accounts))
        all_accounts.update(accounts)
    bw = config.balance_column_width()
    aw = max(chain([10], (len(unicode(a)) for a in all_accounts)))
    width = (bw + 1) * len(balances) + 1 + aw
    if config.output_width() and width > config.output_width():
        aw = max(10, config.output_width() - ((bw + 1) * len(balances) + 1))
    fmt = (u'%{bw}s ' * len(balances) + u' %.{aw}s').format(**locals())
    yield 'PROFIT LOSS STATEMENT'.center(width)
    line = []
    for b in balances:
        line.append(b.date_range.first.strftime(ur'%_d-%b-%Y') if b.date_range.first else '')
    line.append('')
    yield fmt % tuple(line)
    line = []
    for b in balances:
        line.append(b.date_range.last.strftime(ur'%_d-%b-%Y') if b.date_range.last else '')
    line.append('Account')
    yield fmt % tuple(line)
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))
    for section in sections:
        for account in chain([None], sorted((a for a in section.accounts if a.depth() <= section.depth), key=unicode)):
            line = []
            for b in section.balances:
                line.append(config.format_money(b.balance(account)))
            line.append(unicode(account) if account is not None else section.title)
            yield fmt % tuple(line)
        yield fmt % (('-' * bw,) * len(section.balances) + ('-' * aw,))
    line = []
    for b in balances:
        line.append(config.format_money(b.balance(None)))
    line.append('NET PROFIT (LOSS)')
    yield fmt % tuple(line)

def cmd_balance(config, opts):
    chart = get_chart(config, opts)
    acc_pred = parse_option_select_account_predicate(chart, opts)
    all_transactions = get_transactions(chart, config, opts)
    whens, balances = filter_at(chart, all_transactions, opts, acc_pred=acc_pred)
    all_accounts = sorted(frozenset(chain(*(b.accounts for b in balances))), key=unicode)
    logging.debug('all_accounts = %r' % all_accounts)
    aw = max(chain([10], (len(unicode(a)) for a in all_accounts)))
    bw = config.balance_column_width()
    width = (bw + 1) * len(balances) + 1 + aw
    if config.output_width() and width > config.output_width():
        aw = max(10, config.output_width() - ((bw + 1) * len(balances) + 1))
    fmt = (u'%{bw}s ' * len(balances) + u' %.{aw}s').format(**locals())
    yield 'ACCOUNT BALANCES'.center(width)
    yield ''
    line = []
    for when in whens:
        line.append(when.strftime(ur'%_d-%b-%Y'))
    line.append('Account')
    yield fmt % tuple(line)
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))
    for account in all_accounts:
        bals = tuple(b.balance(account) for b in balances)
        if filter(bool, bals) or opts['--all']:
            yield fmt % (tuple(config.format_money(bal) for bal in bals) + (unicode(account),))
    yield fmt % (('-' * bw,) * len(balances) + ('-' * aw,))

def cmd_due(config, opts):
    chart = get_chart(config, opts)
    acc_pred = parse_option_select_account_predicate(chart, opts)
    when = abo.period.parse_when(opts['<when>']) if opts['<when>'] else datetime.date.today()
    transactions = (t for t in get_transactions(chart, config, opts))
    def is_accrual(account):
        return account.atype is abo.account.AccountType.AssetLiability and ('rec' in account.tags or 'pay' in account.tags)
    accounts = defaultdict(lambda: [])
    due_accounts = set()
    for t in transactions:
        for e in t.entries:
            account = chart[e.account]
            if acc_pred(account):
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
            due_all += due.items()
    due_all.sort(key=lambda a: (a[0], sum(e.amount for e in a[1].entries)))
    bw = config.money_column_width()
    fmt = u'%s %s %{bw}s  %s'.format(**locals())
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
        yield fmt % (date.strftime(ur'%a %_d-%b-%Y'),
                     '*' if date < when else '=' if date == when else ' ',
                     config.format_money(balance),
                     u'; '.join([unicode(due.account)] + details))

def get_chart(config, opts):
    return abo.cache.chart_cache(config, opts).get()

def get_transactions(chart, config, opts):
    transactions = []
    for cache in abo.cache.transaction_caches(chart, config, opts):
        transactions += cache.transactions()
    transactions.sort(key=lambda t: (t.date, t.who or '', t.what or '', -t.amount()))
    if opts['--remove']:
        for account in opts['--remove']:
            acc = chart[account]
            transactions = abo.account.remove_account(chart, lambda a: a in acc, transactions)
    return transactions

def parse_option_select_account_predicate(chart, opts):
    return parse_account_predicate(chart, (opts['--select'] or '').lstrip())

def parse_account_predicate(chart, text):
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

def filter_at(chart, transactions, opts, acc_pred=None):
    whens = abo.period.parse_whens(opts['<when>']) if opts['<when>'] else [datetime.date.today()]
    ranges = [abo.balance.Range(None, when) for when in whens]
    balances = [abo.balance.Balance(transactions, range, chart=chart, acc_pred=acc_pred) for range in ranges]
    return whens, balances

def range_line(range):
    p = []
    if range.first is not None:
        p.append('FROM')
        p.append(range.first.strftime(ur'%_d-%b-%Y'))
    if range.last is not None:
        p.append('TO')
        p.append(range.last.strftime(ur'%_d-%b-%Y'))
    return ' '.join(p) if p else 'ALL DATES'

