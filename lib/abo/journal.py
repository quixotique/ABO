# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Journal is a source of Transactions parsed from a text file.

>>> j = Journal(_testconfig, r'''
... type transaction
... date 16/3/2013
... who Somebody
... what something
... db account1 21.90 a debit
... db account2 another debit
... cr "account three" a credit
... amt 22
...
... %default who Some body
... %default bank cash
...
... type invoice
... date 17/3/2013
... what Invoice text
... acc account1
... item income at last
... amt 100
...
... type bill
... date 18/3/2013
... who Another body
... acc account two
... item expense
... gst 8.12
... amt 81.18
...
... %projection
...
... type bill
... date 18/4/2013
... who Another body
... acc account2
... item expense
... gst 9.17
... amt 98.97
...
... %end projection
...
... type receipt
... date 17/4/2013
... what Receipt text
... acc account1
... amt 55.65
...
... type remittance
... date 18/4/2013=30/6/2012
... what Remittance text
... acc account2
... amt 81.11
...
... 7/5/2013=1/1/2013 Somebody; Modern text
...  account one  45.06 ; comment
...  account two  -60.00 ; another comment {31/5/2013}
...  account three ; {+15}
...
... ''')
>>> [t for t in j.transactions() if not t.is_projection] #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 3, 16),
    who='Somebody', what='something',
    entries=(Entry(account='account1', amount=Money.AUD(-21.90), detail='a debit'),
             Entry(account='account2', amount=Money.AUD(-0.10), detail='another debit'),
             Entry(account='account three', amount=Money.AUD(22.00), detail='a credit'))),
 Transaction(date=datetime.date(2013, 3, 17),
    who='Some body', what='Invoice text',
    entries=(Entry(account='account1', amount=Money.AUD(-100.00)),
             Entry(account='income', amount=Money.AUD(100.00), detail='at last'))),
 Transaction(date=datetime.date(2013, 3, 18),
    who='Another body',
    entries=(Entry(account='expense', amount=Money.AUD(-73.06)),
             Entry(account='gst', amount=Money.AUD(-8.12)),
             Entry(account='account two', amount=Money.AUD(81.18)))),
 Transaction(date=datetime.date(2013, 4, 17),
    who='Some body', what='Receipt text',
    entries=(Entry(account='cash', amount=Money.AUD(-55.65)),
             Entry(account='account1', amount=Money.AUD(55.65)))),
 Transaction(date=datetime.date(2013, 4, 18),
    edate=datetime.date(2012, 6, 30),
    who='Some body', what='Remittance text',
    entries=(Entry(account='account2', amount=Money.AUD(-81.11)),
             Entry(account='cash', amount=Money.AUD(81.11)))),
 Transaction(date=datetime.date(2013, 5, 7),
    edate=datetime.date(2013, 1, 1),
    who='Somebody',
    what='Modern text',
    entries=(Entry(account='account two', amount=Money.AUD(-60.00), cdate=datetime.date(2013, 5, 31), detail='another comment'),
             Entry(account='account three', amount=Money.AUD(14.94), cdate=datetime.date(2013, 5, 22)),
             Entry(account='account one', amount=Money.AUD(45.06), detail='comment')))]
>>> [t for t in j.transactions() if t.is_projection] #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 4, 18),
    who='Another body',
    entries=(Entry(account='expense', amount=Money.AUD(-89.80)),
             Entry(account='gst', amount=Money.AUD(-9.17)),
             Entry(account='account2', amount=Money.AUD(98.97))))]

"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.config
    import abo.journal
    abo.journal._testconfig = abo.config.Config()
    doctest.testmod(abo.journal)

import sys
import logging
import os
import re
import shlex
import subprocess
import datetime
import copy
from abo.transaction import Transaction
import abo.account
import abo.text
import abo.text
from abo.types import struct

class ParseException(abo.text.LineError):
    def __init__(self, source, message):
        abo.text.LineError.__init__(self, str(message), line=source)

class Journal(object):

    def __init__(self, config, source_file, chart=None):
        self.config = config
        self.chart = chart
        self.source_file = source_file

    def transactions(self):
        return self._parse(self.source_file)

    _regex_filter = re.compile(r'^%filter\s+(.*)$', re.MULTILINE)

    def _parse(self, source_file):
        if isinstance(source_file, str):
            # To facilitate testing.
            import io
            source_file = io.StringIO(source_file)
            source_file.name = 'StringIO'
            source_path = None
        else:
            source_path = source_file.name if os.path.exists(source_file.name) else None
        name = getattr(source_file, 'name', str(source_file))
        logging.info("parse %r", name)
        lines = list(source_file)
        m = self._regex_filter.search(''.join(lines[:10]))
        if m:
            args = shlex.split(m.group(1))
            if source_path is not None:
                expanded = False
                for i in range(len(args)):
                    if args[i] == '{}':
                        args[i] = source_path
                        expanded = True
                if not expanded:
                    args.append(source_path)
                out = subprocess.check_output(args, cwd=self.config.basedir, stdin=open('/dev/null'))
            else:
                out, err = subprocess.Popen(args,
                                            cwd=self.config.basedir,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE)\
                                     .communicate(''.join(lines).encode())
            import io
            lines = list(io.StringIO(out.decode()))
        lines = [line.rstrip('\n') for line in lines]
        lines = abo.text.number_lines(lines, name=source_file.name)
        blocks = abo.text.line_blocks(lines)
        template = {
            'type': None,
            'date': None,
            'due': None,
            'who': None,
            'what': None,
            'db': [],
            'cr': [],
            'acc': None,
            'item': [],
            'bank': None,
            'gst': None,
            'amt': None,
        }
        defaults = copy.deepcopy(template)
        in_projection = False
        self._period = None
        for block in blocks:
            firstline = None
            ledger_date = None
            ledger_what = None
            ledger_lines = []
            tags = copy.deepcopy(template)
            percent_block = None
            for line in block:
                words = line.split(None, 1)
                if not words:
                    continue
                if words[0].startswith('%'):
                    if percent_block is False:
                        raise ParseException(line, 'at ' + words[0] + ': not permitted within transaction')
                    percent_block = True
                if words[0] == '%default':
                    try:
                        self._parse_line_tagtext(line, words[1])
                    except ParseException:
                        raise ParseException(line, 'in %default: ' + e)
                    if line.tag not in defaults:
                        raise ParseException(line, 'invalid %%default tag %r' % line.tag)
                    if not line.text:
                        defaults[line.tag] = None
                    elif type(template[line.tag]) is list:
                        defaults[line.tag] = [line]
                    else:
                        defaults[line.tag] = line
                elif words[0] == '%period':
                    self._period = None
                    if len(words) > 1:
                        try:
                            start, end = list(map(self._parse_date, words[1].split(None, 1)))
                        except (IndexError, ValueError):
                            raise ParseException(line, 'invalid %period arguments')
                        if (    end <= start
                            or  end >= start + datetime.timedelta(days=366)
                            or  (end.year != start.year and end.replace(year=start.year) >= start)):
                            raise ParseException(line, 'invalid %period date range')
                        self._period = (start, end)
                elif words[0] == '%projection':
                    if len(words) > 1:
                        raise ParseException(line, 'spurious %projection arguments')
                    if in_projection:
                        raise ParseException(line, 'unexpected %projection (missing %end projection)')
                    in_projection = True
                elif words[0] == '%end':
                    if len(words) < 2:
                        raise ParseException(line, 'missing %end argument')
                    if words[1] == 'projection':
                        if not in_projection:
                            raise ParseException(line, 'unexpected %end projection (missing %projection?)')
                        in_projection = False
                    else:
                        raise ParseException(line, 'unsupported %end argument')
                if words[0].startswith('%'):
                    continue
                percent_block = False
                if ledger_date:
                    if line[0].isspace():
                        ledger_lines.append(line.lstrip())
                    else:
                        raise ParseException(line, 'should be indented')
                else:
                    self._parse_line_tagtext(line, line)
                    if line.tag in tags:
                        if not firstline:
                            firstline = line
                        if type(tags[line.tag]) is list:
                            tags[line.tag].append(line)
                        elif tags[line.tag] is None:
                            tags[line.tag] = line
                        else:
                            raise ParseException(line, 'duplicate tag %r' % line.tag)
                        continue
                    elif not firstline:
                        try:
                            ledger_date = self._parse_date_edate(line.tag)
                            ledger_what = line.text
                        except ValueError:
                            raise ParseException(line, 'invalid date %r' % line.tag)
                    else:
                        raise ParseException(line, 'invalid tag %r' % line.tag)
            kwargs = None
            if firstline:
                kwargs = self._parse_legacy_block(firstline, tags, defaults)
            elif ledger_date:
                kwargs = self._parse_ledger_block(ledger_date, ledger_what, ledger_lines)
            if kwargs:
                line = firstline or ledger_lines[0]
                if len(kwargs['entries']) < 2:
                    raise ParseException(line, 'too few entries')
                for entry in kwargs['entries']:
                    del entry['line']
                kwargs['is_projection'] = in_projection
                try:
                    yield Transaction(**kwargs)
                except:
                    abo.text.raise_with_context(line)
                    raise

    _regex_ledger_due = re.compile(r'\s*{([^}]*)}\s*')

    def _parse_ledger_block(self, ledger_date, ledger_what, ledger_lines):
        if ';' in ledger_what:
            who, what = map(str.strip, str(ledger_what).split(';', 1))
        else:
            who = None
            what = str(ledger_what).strip()
        entries = []
        noamt = None
        for line in ledger_lines:
            entry = {'line': line}
            if ';' in line:
                line, detail = line.split(';', 1)
                m = self._regex_ledger_due.search(detail)
                if m:
                    entry['cdate'] = self._parse_date(m.group(1), relative_to=ledger_date[0])
                    detail = (detail[:m.start(0)] + ' ' + detail[m.end(0):])
                entry['detail'] = str(detail).strip()
            line = line.rstrip()
            if '  ' in line:
                acc, amt = line.rsplit('  ', 1)
                acc = str(acc.strip())
                amt = amt.strip()
                try:
                    amount = self.config.parse_money(amt)
                except ValueError:
                    raise ParseException(line, 'invalid amount %r' % amt)
                if amount == 0:
                    raise ParseException(line, 'zero amount')
                entry['amount'] = amount
            else:
                acc = str(line.strip())
                if noamt:
                    raise ParseException(line, 'missing amount')
                noamt = entry
            if self.chart:
                try:
                    entry['account'] = self.chart[acc]
                except (ValueError, KeyError) as e:
                    raise ParseException(line, e)
                if not entry['account'].is_substantial():
                    raise ParseException(line, 'insubstantial account %r' % str(entry['account']))
            else:
                entry['account'] = acc
            entries.append(entry)
        if noamt:
            total = sum(entry['amount'] for entry in entries if 'amount' in entry)
            if total == 0:
                raise ParseException(noamt['line'], 'other entries sum to zero')
            noamt['amount'] = -total
        kwargs = {}
        kwargs['date'], kwargs['edate'] = ledger_date
        kwargs['who'] = who
        kwargs['what'] = what
        kwargs['entries'] = entries
        return kwargs

    def _parse_legacy_block(self, firstline, tags, defaults):
        used = dict((tag, False) for tag in tags if tags[tag])
        def tagline(tag, optional=False):
            line = tags[tag]
            if line is None or (type(line) is list and not line):
                line = defaults[tag]
            #print 'tag=%r line=%r' % (tag, line,)
            if not line and not optional:
                raise ParseException(firstline, 'missing tag %r' % tag)
            used[tag] = True
            return line
        meth = getattr(self, '_parse_type_' + tagline('type').text, None)
        if not meth:
            raise ParseException(tags['type'], 'unknown type %r' % (tags['type'].text,))
        kwargs = {}
        kwargs['date'], kwargs['edate'] = self._parse_date_edate(tagline('date').text)
        who = tagline('who', optional=True)
        kwargs['who'] = str(who.text) if who else None
        what = tagline('what', optional=True)
        kwargs['what'] = str(what.text) if what else None
        kwargs['entries'] = meth(firstline, kwargs, tagline)
        for tag in used:
            if not used[tag]:
                line = tags[tag]
                if type(line) is list:
                    line = line[0]
                raise ParseException(line, 'spurious %r tag' % (tag,))
        return kwargs

    def _parse_line_tagtext(cls, line, text):
        words = text.split(None, 1)
        if len(words) == 2:
            line.tag, line.text = str(words[0]), words[1]
        elif len(words) == 1:
            line.tag, line.text = str(words[0]), ''
        else:
            raise ParseException(line, 'expecting <tag> [value]')

    def _parse_type_transaction(self, firstline, kwargs, tagline):
        amt = tagline('amt', optional=True)
        amount = self._parse_money(amt) if amt else None
        if amount is not None and amount < 0:
            raise ParseException(amt, 'negative amount not allowed: %s' % amount)
        entries = []
        totals = {'db': 0, 'cr': 0}
        entries_noamt = {'db': None, 'cr': None}
        for dbcr, sign in (('db', -1), ('cr', 1)):
            for line in tagline(dbcr):
                if not line.text:
                    raise ParseException(line, 'empty tag %r' % line.tag)
                entry = self._parse_dbcr(line)
                if 'amount' in entry:
                    totals[dbcr] += entry['amount']
                    entry['amount'] *= sign
                    entries.append(entry)
                elif entries_noamt[dbcr] is None:
                    entries_noamt[dbcr] = entry
                else:
                    raise ParseException(line, '%s missing amount' % (dbcr,))
        if amount is None:
            if not entries:
                raise ParseException(firstline, "missing 'amt'")
            amount = max(totals.values())
        for dbcr, sign, desc in (('db', -1, 'debit'), ('cr', 1, 'credit')):
            if totals[dbcr] > amount:
                raise ParseException(firstline, '%ss (%s) exceed amount (%s) by %s' % (desc, totals[dbcr], amount, totals[dbcr] - amount))
            elif totals[dbcr] < amount:
                if entries_noamt[dbcr] is not None:
                    entries_noamt[dbcr]['amount'] = (amount - totals[dbcr]) * sign
                    entries.append(entries_noamt[dbcr])
                else:
                    raise ParseException(firstline, '%ss (%s) sum below amount (%s) by %s' % (desc, totals[dbcr], amount, amount - totals[dbcr] ))
            elif entries_noamt[dbcr] is not None:
                raise ParseException(entries_noamt[dbcr]['line'], 'nil entry; %ss already sum to amount (%s)' % (desc, amount,))
        return entries

    def _parse_invoice_bill(self, firstline, kwargs, tagline, sign):
        due = tagline('due', optional=True)
        cdate = self._parse_date(due.text, relative_to=kwargs['date']) if due else None
        amt = tagline('amt', optional=True)
        amount = self._parse_money(amt) if amt else None
        if amount is not None and amount == 0:
            raise ParseException(amt, 'zero amount not allowed: %s' % amount)
        entries = []
        acc = tagline('acc', optional=True)
        account = self._parse_account_label(acc.text)
        total = 0
        gst = tagline('gst', optional=True)
        gst_amount = self._parse_money(gst) if gst else None
        if gst_amount is not None:
            if gst_amount == 0:
                raise ParseException(amt, 'zero gst amount not allowed: %s' % gst_amount)
            gst_account = self._gst_account_invoice(gst) if sign < 0 else self._gst_account_bill(gst) 
            total += gst_amount
            entries.append({'line': gst, 'account': gst_account, 'amount': gst_amount * -sign})
        entry_noamt = None
        for line in tagline('item'):
            entry = self._parse_dbcr(line)
            if 'amount' in entry:
                total += entry['amount']
                entry['amount'] *= -sign
                entries.append(entry)
            elif entry_noamt is None:
                entry_noamt = entry
            else:
                raise ParseException(line, "'item' missing amount")
        if amount is None:
            if not entries:
                raise ParseException(firstline, "missing 'amt'")
            amount = total
        elif total != amount:
            if entry_noamt is not None:
                entry_noamt['amount'] = (amount - total) * -sign
                entries.append(entry_noamt)
            else:
                raise ParseException(firstline, 'items (%s) sum below amount (%s) by %s' % (total, amount, amount - total))
        elif entry_noamt is not None:
            raise ParseException(entry_noamt['line'], 'nil entry; items already sum to amount (%s)' % (amount,))
        entries.append({'line': acc, 'account': account, 'amount': amount * sign, 'cdate': cdate})
        return entries

    def _parse_type_invoice(self, firstline, kwargs, tagline):
        return self._parse_invoice_bill(firstline, kwargs, tagline, -1)

    def _parse_type_bill(self, firstline, kwargs, tagline):
        return self._parse_invoice_bill(firstline, kwargs, tagline, 1)

    def _parse_remittance_receipt(self, firstline, kwargs, tagline, sign):
        amount = self._parse_money(tagline('amt'))
        acc = tagline('acc')
        account = self._parse_account_label(acc.text)
        bank = tagline('bank')
        bank_account = self._parse_account_label(bank.text)
        entries = []
        entries.append({'line': acc, 'account': account, 'amount': amount * sign})
        entries.append({'line': bank, 'account': bank_account, 'amount': amount * -sign})
        return entries

    def _parse_type_remittance(self, firstline, kwargs, tagline):
        return self._parse_remittance_receipt(firstline, kwargs, tagline, -1)

    def _parse_type_receipt(self, firstline, kwargs, tagline):
        return self._parse_remittance_receipt(firstline, kwargs, tagline, 1)

    _regex_relative = re.compile(r'^[+-]\d+$')

    def _parse_date(self, text, relative_to=None):
        d = None
        enforce = True
        if text.endswith("!"):
            enforce = False
            text = text[:-1]
        if relative_to is not None:
            dmy = text.split('/', 2)
            if len(dmy) == 3:
                if not dmy[0]:
                    dmy[0] = '%u' % relative_to.day
                if not dmy[1]:
                    dmy[1] = '%u' % relative_to.month
                if not dmy[2]:
                    dmy[2] = '%04u' % relative_to.year
                text = '/'.join(dmy)
        try:
            d = datetime.datetime.strptime(text, '%d/%m/%Y').date()
        except ValueError:
            if self._period:
                enforce = True
                try:
                    d = datetime.datetime.strptime(text + '/%04u' % self._period[0].year, '%d/%m/%Y').date()
                    if d < self._period[0]:
                        d = None
                except ValueError:
                    pass
                if d is None and self._period[0].year != self._period[1].year:
                    try:
                        d = datetime.datetime.strptime(text + '/%04u' % self._period[1].year, '%d/%m/%Y').date()
                    except ValueError:
                        pass
        if d is not None:
            if enforce and self._period and (d < self._period[0] or d > self._period[1]):
                raise ParseException(text, 'date %s outside period' % text)
            return d
        if relative_to is not None and self._regex_relative.match(text):
            return relative_to + datetime.timedelta(int(text))
        raise ParseException(text, 'invalid date %r' % text)

    def _parse_date_edate(self, text):
        texts = text.split('=', 1)
        date = self._parse_date(texts[0])
        edate = self._parse_date(texts[1], relative_to=date) if len(texts) > 1 else None
        return date, edate

    def _gst_account_bill(self, line):
        # TODO: move these account names into configuration
        if self.chart:
            try:
                return self.chart['gst_credit']
            except KeyError:
                pass
            try:
                return self.chart['gst']
            except KeyError as e:
                raise ParseException(line, e)
        try:
            return 'gst'
        except ValueError as e:
            raise ParseException(line, e)

    def _gst_account_invoice(self, line):
        # TODO: move these account names into configuration
        if self.chart:
            try:
                return self.chart['gst_sales']
            except KeyError:
                pass
            try:
                return self.chart['gst']
            except KeyError as e:
                raise ParseException(line, e)
        try:
            return 'gst'
        except ValueError as e:
            raise ParseException(line, e)

    def _parse_account_label(self, text):
        if self.chart:
            try:
                account = self.chart[str(text)]
            except (ValueError, KeyError) as e:
                raise ParseException(text, e)
            if not account.is_substantial():
                raise ParseException(text, 'insubstantial account %r' % account.label)
            return account
        else:
            return str(text)

    def _parse_money(self, line):
        try:
            return self.config.parse_money(line.text)
        except ValueError:
            raise ParseException(line, 'invalid amount %r' % line.text)

    def _parse_dbcr(self, line):
        entry = {'line': line}
        word, text = self._popword(str(line.text))
        assert word, "line.text=%r word=%r" % (line.text, word,)
        entry['account'] = self._parse_account_label(word)
        money = None
        word, detail = self._popword(text)
        if word and self.appears_money(word):
            try:
                money = self.config.parse_money(word)
            except ValueError:
                detail = text
        else:
            detail = text
        if detail:
            entry['detail'] = detail
        if money is not None:
            entry['amount'] = money
        return entry

    _regex_word = re.compile(r'(?:"([^"]+)"|(\S+))(?=$|\s)')

    @classmethod
    def _popword(cls, text):
        m = cls._regex_word.match(text)
        if m:
            remain = text[m.end(0):].lstrip()
            return (m.group(1), remain) if m.group(1) else (m.group(2) or '', remain)
        return ('', '')

    _regex_amount = re.compile(r'\d*\.\d+|\d+')

    @classmethod
    def appears_money(cls, text):
        return cls._regex_amount.search(text) is not None

__test__ = {
'transaction':r"""

>>> list(Journal(_testconfig, r'''
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money.AUD(-10.00)),
             Entry(account='bank', amount=Money.AUD(10.00))))]

>>> list(Journal(_testconfig, r'''
... type transaction
... date 22/2/2013
... who Somebody Else
... what another thing
... db food 7
... db drink 3 beer
... cr bank 10
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 22),
    who='Somebody Else', what='another thing',
    entries=(Entry(account='food', amount=Money.AUD(-7.00)),
             Entry(account='drink', amount=Money.AUD(-3.00), detail='beer'),
             Entry(account='bank', amount=Money.AUD(10.00))))]

>>> list(Journal(_testconfig, r'''
... type transaction
... date 23/2/2013
... who Whoever
... what whatever
... db food 7
... db drink beer
... cr bank
... cr cash 2
... amt 10
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 23),
    who='Whoever', what='whatever',
    entries=(Entry(account='food', amount=Money.AUD(-7.00)),
             Entry(account='drink', amount=Money.AUD(-3.00), detail='beer'),
             Entry(account='cash', amount=Money.AUD(2.00)),
             Entry(account='bank', amount=Money.AUD(8.00))))]

>>> list(Journal(_testconfig, r'''
... %default type transaction
... %default cr cash
... %default db games
...
... date 23/2/2013
... who Whoever
... what whatever
... db food 7
... db drink beer
... amt 10
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 23),
    who='Whoever', what='whatever',
    entries=(Entry(account='food', amount=Money.AUD(-7.00)),
             Entry(account='drink', amount=Money.AUD(-3.00), detail='beer'),
             Entry(account='cash', amount=Money.AUD(10.00))))]

>>> list(Journal(_testconfig, r'''
... date 23/2/2013
... type transaction
... # comment
... who Whoever
... #line 20 "wah"
... what whatever
... db
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
abo.journal.ParseException: "wah", 21: empty tag 'db'

>>> list(Journal(_testconfig, r'''
... type transaction
... date 21/2/2013
... due 21/3/2013
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
abo.journal.ParseException: StringIO, 4: spurious 'due' tag

>>> list(Journal(_testconfig, r'''
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food
... cr bank
... item food
... amt 10.00
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
abo.journal.ParseException: StringIO, 8: spurious 'item' tag

>>> list(Journal(_testconfig, r'''
... %default due 21/3/2013
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food 10
... cr bank
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money.AUD(-10.00)),
             Entry(account='bank', amount=Money.AUD(10.00))))]

""",
'invoice':r"""

>>> list(Journal(_testconfig, r'''
... type invoice
... date 21/2/2013
... due 21/3/2013
... who Somebody
... what something
... acc body
... item thing comment
... amt 100
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='body', amount=Money.AUD(-100.00), cdate=datetime.date(2013, 3, 21)),
             Entry(account='thing', amount=Money.AUD(100.00), detail='comment')))]

""",
'bill':r"""

>>> list(Journal(_testconfig, r'''
... type bill
... date 1/2/2013
... due +14
... who Somebody
... what something
... acc body
... item thing comment
... item round .01 oops
... gst .11
... amt 1.01
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 1),
    who='Somebody', what='something',
    entries=(Entry(account='thing', amount=Money.AUD(-0.89), detail='comment'),
             Entry(account='gst', amount=Money.AUD(-0.11)),
             Entry(account='round', amount=Money.AUD(-0.01), detail='oops'),
             Entry(account='body', amount=Money.AUD(1.01), cdate=datetime.date(2013, 2, 15))))]

""",
'remittance':r"""

>>> list(Journal(_testconfig, r'''
... type remittance
... date 15/2/2013
... who Somebody
... what something
... acc body
... bank cash
... amt 1.01
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='Somebody', what='something',
    entries=(Entry(account='body', amount=Money.AUD(-1.01)),
             Entry(account='cash', amount=Money.AUD(1.01))))]

""",
'receipt':r"""

>>> list(Journal(_testconfig, r'''
... type receipt
... date 15/2/2013
... who Somebody
... what something
... acc body
... bank cash
... amt 55.65
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='Somebody', what='something',
    entries=(Entry(account='cash', amount=Money.AUD(-55.65)),
             Entry(account='body', amount=Money.AUD(55.65))))]

""",
'filter':r"""

>>> list(Journal(_testconfig, r'''
... %filter m4 --synclines
... define(`some', `any')
... type receipt
... date 15/2/2013
... who some body
... what some thing
... acc body
... bank cash
... amt 55.65
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='any body', what='any thing',
    entries=(Entry(account='cash', amount=Money.AUD(-55.65)),
             Entry(account='body', amount=Money.AUD(55.65))))]

""",
'period':r"""

>>> list(Journal(_testconfig, r'''
... %period 1/7/2012 30/6/2013
... type transaction
... date 28/2
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 28),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money.AUD(-10.00)),
             Entry(account='bank', amount=Money.AUD(10.00))))]

>>> list(Journal(_testconfig, r'''
... %period 1/7/2012 30/6/2013
... type transaction
... date 29/2
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions()) #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
abo.journal.ParseException: StringIO, 4: invalid date '29/2'

""",
}
