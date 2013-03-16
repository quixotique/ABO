# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Journal is a source of Transactions parsed from a text file.

>>>
"""

import locale
import re
import shlex
import subprocess
import datetime
import copy
from abo.transaction import Transaction
import abo.config
import abo.account
from abo.types import struct

class Journal(object):

    def __init__(self, source_file):
        self.source_file = source_file
        self._transactions = None

    def transactions(self):
        if self._transactions is None:
            self._parse(self.source_file)
        return self._transactions

    _regex_encoding = re.compile(r'coding[=:]\s*([-\w.]+)', re.MULTILINE)
    _regex_filter = re.compile(r'^%filter\s+(.*)$', re.MULTILINE)

    def _parse(self, source_file):
        self._transactions = []
        if isinstance(source_file, basestring):
            # To facilitate testing.
            import StringIO
            source_file = StringIO.StringIO(source_file)
            source_file.name = 'StringIO'
        lines = list(source_file)
        name = getattr(source_file, 'name', str(source_file))
        m = self._regex_encoding.search('\n'.join(lines[:10]))
        encoding = m.group(1) if m else locale.getlocale()[1]
        m = self._regex_filter.search('\n'.join(lines[:10]))
        if m:
            args = shlex.split(m.group(1))
            if type(source_file) is file:
                expanded = False
                for i in xrange(len(args)):
                    if args[i] == '{}':
                        args[i] = name
                        expanded = True
                if not expanded:
                    args.append(name)
                out = subprocess.check_output(args, stdin=file('/dev/null'))
            else:
                out, err = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate(''.join(lines))
            out = out.decode(encoding)
            import StringIO
            lines = list(StringIO.StringIO(out))
        else:
            lines = [line.decode(encoding) for line in lines]
        blocks = []
        block = []
        lnum = 0
        for line in lines:
            line = line.rstrip('\n')
            lnum += 1
            if line:
                words = line.split(None, 3)
                if words[0] == '#line' and len(words) > 1 and words[1].isdigit():
                    lnum = int(words[1]) - 1
                    if len(words) > 2:
                        name = words[2]
                elif not words[0].startswith('#'):
                    block.append(struct(name=name, line_number=lnum, fulltext=line))
            elif block:
                blocks.append(block)
                block = []
        if block:
            blocks.append(block)
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
            'amt': None,
        }
        defaults = copy.deepcopy(template)
        for block in blocks:
            firstline = None
            tags = copy.deepcopy(template)
            for line in block:
                words = line.fulltext.split(None, 1)
                if words[0] == '%default':
                    try:
                        self._parse_line_tagtext(line, words[1])
                    except ParseException:
                        raise ParseException(line, 'in %%default: ' + e)
                    if line.tag not in defaults:
                        raise ParseException(line, 'invalid %%default tag %r' % line.tag)
                    if not line.text:
                        defaults[line.tag] = None
                    elif type(template[line.tag]) is list:
                        defaults[line.tag] = [line]
                    else:
                        defaults[line.tag] = line
                    continue
                if words[0].startswith('%'):
                    continue
                self._parse_line_tagtext(line, line.fulltext)
                if line.tag not in tags:
                    raise ParseException(line, 'invalid tag %r' % line.tag)
                if not firstline:
                    firstline = line
                if type(tags[line.tag]) is list:
                    tags[line.tag].append(line)
                elif tags[line.tag] is None:
                    tags[line.tag] = line
                else:
                    raise ParseException(line, 'duplicate tag %r' % line.tag)
            if not firstline:
                continue
            used = dict((tag, False) for tag in tags if tags[tag])
            def tagline(tag, optional=False):
                line = tags.get(tag) or defaults.get(tag)
                if not line and not optional:
                    raise ParseException(firstline, 'missing tag %r' % tag)
                used[tag] = True
                return line
            meth = getattr(self, '_parse_type_' + tagline('type').text, None)
            if not meth:
                raise ParseException(tags['type'], 'unknown type %r' % (tags['type'].text,))
            kwargs = {}
            kwargs['date'] = self._parse_date(tagline('date'))
            who = tagline('who', optional=True)
            kwargs['who'] = who.text if who else None
            kwargs['what'] = tagline('what').text
            entries = meth(firstline, kwargs, tagline)
            for tag in used:
                if not used[tag]:
                    line = tags[tag]
                    if type(line) is list:
                        line = line[0]
                    raise ParseException(line, 'spurious %r tag' % (tag,))
            for entry in entries:
                del entry['line']
            kwargs['entries'] = entries
            self._transactions.append(Transaction(**kwargs))

    def _parse_line_tagtext(cls, line, text):
        words = text.split(None, 1)
        if len(words) == 2:
            line.tag, line.text = words
        elif len(words) == 1:
            line.tag, line.text = words[0], ''
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
        cdate = self._parse_date(due, relative_to=kwargs['date']) if due else None
        amt = tagline('amt', optional=True)
        amount = self._parse_money(amt) if amt else None
        if amount is not None and amount == 0:
            raise ParseException(amt, 'zero amount not allowed: %s' % amount)
        entries = []
        acc = tagline('acc')
        account = self._parse_account_name(acc)
        total = 0
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
        account = self._parse_account_name(acc)
        bank = tagline('bank')
        bank_account = self._parse_account_name(bank)
        entries = []
        entries.append({'line': acc, 'account': account, 'amount': amount * sign})
        entries.append({'line': bank, 'account': bank_account, 'amount': amount * -sign})
        return entries

    def _parse_type_remittance(self, firstline, kwargs, tagline):
        return self._parse_remittance_receipt(firstline, kwargs, tagline, -1)

    def _parse_type_receipt(self, firstline, kwargs, tagline):
        return self._parse_remittance_receipt(firstline, kwargs, tagline, 1)

    _regex_relative = re.compile(r'^[+-]\d+$')

    @classmethod
    def _parse_date(cls, line, relative_to=None):
        try:
            return datetime.datetime.strptime(line.text, '%d/%m/%Y').date()
        except ValueError:
            if relative_to is not None and cls._regex_relative.match(line.text):
                return relative_to + datetime.timedelta(int(line.text))
            raise ParseException(line, 'invalid date %r' % line.text)

    @classmethod
    def _parse_account_name(cls, line):
        try:
            return abo.account.parse_account_name(line.text)
        except ValueError, e:
            raise ParseException(line, e)

    @classmethod
    def _parse_money(cls, line):
        try:
            return abo.config.parse_money(line.text)
        except ValueError:
            raise ParseException(line, 'invalid amount %r' % line.text)

    @classmethod
    def _parse_dbcr(cls, line):
        entry = {'line': line}
        text = line.text
        word, text = cls._popword(text)
        try:
            entry['account'] = abo.account.parse_account_name(word)
        except ValueError:
            raise ParseException(line, e)
        money = None
        word, detail = cls._popword(text)
        if word and cls.appears_money(word):
            try:
                money = abo.config.parse_money(word)
            except ValueError:
                raise ParseException(line, 'invalid amount %r' % word)
        else:
            detail = text
        if detail:
            entry['detail'] = text
        if money is not None:
            entry['amount'] = money
        return entry

    @staticmethod
    def _popword(text):
        words = text.split(None, 1)
        return tuple(words) if len(words) == 2 else (words[0], '') if len(words) == 1 else ('', '')

    _regex_amount = re.compile(r'\d*\.\d+|\d+')

    @classmethod
    def appears_money(cls, text):
        return cls._regex_amount.search(text) is not None

class ParseException(Exception):

    def __init__(self, source, message):
        s = []
        if hasattr(source, 'name'):
            s.append(str(source.name))
        if hasattr(source, 'line_number'):
            s.append(str(source.line_number))
        s = ', '.join(s) + ': ' if s else ''
        super(ParseException, self).__init__('%s%s' % (s, message))

__test__ = {
'transaction':r"""

>>> Journal(r'''
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money(-10.00, Currencies.AUD)),
             Entry(account='bank', amount=Money(10.00, Currencies.AUD))))]

>>> Journal(r'''
... type transaction
... date 22/2/2013
... who Somebody Else
... what another thing
... db food 7
... db drink 3 beer
... cr bank 10
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 22),
    who='Somebody Else', what='another thing',
    entries=(Entry(account='food', amount=Money(-7.00, Currencies.AUD)),
             Entry(account='drink', amount=Money(-3.00, Currencies.AUD), detail='beer'),
             Entry(account='bank', amount=Money(10.00, Currencies.AUD))))]

>>> Journal(r'''
... type transaction
... date 23/2/2013
... who Whoever
... what whatever
... db food 7
... db drink beer
... cr bank
... cr cash 2
... amt 10
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 23),
    who='Whoever', what='whatever',
    entries=(Entry(account='food', amount=Money(-7.00, Currencies.AUD)),
             Entry(account='drink', amount=Money(-3.00, Currencies.AUD), detail='beer'),
             Entry(account='cash', amount=Money(2.00, Currencies.AUD)),
             Entry(account='bank', amount=Money(8.00, Currencies.AUD))))]

>>> Journal(r'''
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
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 23),
    who='Whoever', what='whatever',
    entries=(Entry(account='food', amount=Money(-7.00, Currencies.AUD)),
             Entry(account='drink', amount=Money(-3.00, Currencies.AUD), detail='beer'),
             Entry(account='cash', amount=Money(10.00, Currencies.AUD))))]

>>> Journal(r'''
... date 23/2/2013
... # comment
... who Whoever
... #line 20 "wah"
... what whatever
... db
... ''') #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
ParseException: "wah", 22: syntax error, expecting "<tag> <text>"

>>> Journal(r'''
... type transaction
... date 21/2/2013
... due 21/3/2013
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
ParseException: StringIO, 3: spurious 'due' tag

>>> Journal(r'''
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food
... cr bank
... item food
... amt 10.00
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
ParseException: StringIO, 7: spurious 'item' tag

>>> Journal(r'''
... %default due 21/3/2013
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food 10
... cr bank
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money(-10.00, Currencies.AUD)),
             Entry(account='bank', amount=Money(10.00, Currencies.AUD))))]

""",
'invoice':r"""

>>> Journal(r'''
... type invoice
... date 21/2/2013
... due 21/3/2013
... who Somebody
... what something
... acc body
... item thing comment
... amt 100
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='body', amount=Money(-100.00, Currencies.AUD), cdate=datetime.date(2013, 3, 21)),
             Entry(account='thing', amount=Money(100.00, Currencies.AUD), detail='comment')))]

""",
'bill':r"""

>>> Journal(r'''
... type bill
... date 1/2/2013
... due +14
... who Somebody
... what something
... acc body
... item thing comment
... item round .01 oops
... amt 1.01
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 1),
    who='Somebody', what='something',
    entries=(Entry(account='thing', amount=Money(-1.00, Currencies.AUD), detail='comment'),
             Entry(account='round', amount=Money(-0.01, Currencies.AUD), detail='oops'),
             Entry(account='body', amount=Money(1.01, Currencies.AUD), cdate=datetime.date(2013, 2, 15))))]

""",
'remittance':r"""

>>> Journal(r'''
... type remittance
... date 15/2/2013
... who Somebody
... what something
... acc body
... bank cash
... amt 1.01
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='Somebody', what='something',
    entries=(Entry(account='cash', amount=Money(-1.01, Currencies.AUD)),
             Entry(account='body', amount=Money(1.01, Currencies.AUD))))]

""",
'receipt':r"""

>>> Journal(r'''
... type receipt
... date 15/2/2013
... who Somebody
... what something
... acc body
... bank cash
... amt 55.65
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='Somebody', what='something',
    entries=(Entry(account='body', amount=Money(-55.65, Currencies.AUD)),
             Entry(account='cash', amount=Money(55.65, Currencies.AUD))))]

""",
'filter':r"""

>>> Journal(r'''
... %filter m4 --synclines
... define(`some', `any')
... type receipt
... date 15/2/2013
... who some body
... what some thing
... acc body
... bank cash
... amt 55.65
... ''').transactions() #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 15),
    who='any body', what='any thing',
    entries=(Entry(account='body', amount=Money(-55.65, Currencies.AUD)),
             Entry(account='cash', amount=Money(55.65, Currencies.AUD))))]

""",
}

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
