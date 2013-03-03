# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Journal is a source of Transactions parsed from a text file.

>>>
"""

import re
import datetime
import copy
from abo.transaction import Transaction
import abo.config
from abo.struct import struct

class Journal(object):

    def __init__(self, source_file):
        self.transactions = []
        self._parse(source_file)

    def _parse(self, source_file):
        if isinstance(source_file, basestring):
            # To facilitate testing.
            import StringIO
            source_file = StringIO.StringIO(source_file)
            source_file.name = 'StringIO'
        lines = list(source_file)
        blocks = []
        block = []
        lnum = 0
        name = getattr(source_file, 'name', str(source_file))
        for line in lines:
            line = line.rstrip('\n')
            if line:
                words = line.split(None, 3)
                if words[0] == '#line' and len(words) > 1 and words[1].isdigit():
                    lnum = int(words[1])
                    if len(words) > 2:
                        name = words[2]
                elif words[0].startswith('#'):
                    lnum += 1
                else:
                    lnum += 1
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
            tags = copy.deepcopy(template)
            for line in block:
                words = line.fulltext.split(None, 1)
                if words[0] == '%default':
                    try:
                        line.tag, line.text = words[1].split(None, 1)
                    except ValueError, e:
                        raise ParseException(line, 'syntax error, expecting "%default <tag> <text>"')
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
                try:
                    line.tag, line.text = line.fulltext.split(None, 1)
                except ValueError, e:
                    raise ParseException(line, 'syntax error, expecting "<tag> <text>"')
                if line.tag not in tags:
                    raise ParseException(line, 'invalid tag %r' % line.tag)
                if type(tags[line.tag]) is list:
                    tags[line.tag].append(line)
                elif tags[line.tag] is None:
                    tags[line.tag] = line
                else:
                    raise ParseException(line, 'duplicate tag %r' % line.tag)
            used = dict((tag, False) for tag in tags if tags[tag])
            if not used:
                continue
            def tagline(tag, optional=False):
                line = tags.get(tag) or defaults.get(tag)
                if not line and not optional:
                    raise ParseException(block[0], 'missing tag %r', tag)
                used[tag] = True
                return line
            kwargs = {}
            kwargs['date'] = self._parse_date(tagline('date'))
            kwargs['who'] = tagline('who').text
            kwargs['what'] = tagline('what').text
            amt = tagline('amt', optional=True)
            amount = self._parse_money(amt) if amt else None
            if tagline('type').text == 'transaction':
                entries = []
                totals = {'db': 0, 'cr': 0}
                entries_noamt = {'db': None, 'cr': None}
                for dbcr, sign in (('db', -1), ('cr', 1)):
                    for line in tagline(dbcr):
                        words = line.text.split(None, 2)
                        entry = {'line': line}
                        money = None
                        entry['account'] = words.pop(0)
                        if words and self.appears_money(words[0]):
                            try:
                                money = abo.config.parse_money(words.pop(0))
                            except ValueError:
                                raise ParseException(line, 'invalid amount %r' % words[1])
                        if words:
                            entry['detail'] = words.pop(0)
                        assert not words
                        if money is not None:
                            entry['amount'] = money * sign
                            entries.append(entry)
                            totals[dbcr] += money
                        elif entries_noamt[dbcr] is None:
                            entries_noamt[dbcr] = entry
                        else:
                            raise ParseException(line, '%s missing amount' % (dbcr,))
                if amount is None and entries:
                    amount = max(totals.values())
                for dbcr, sign, desc in (('db', -1, 'debit'), ('cr', 1, 'credit')):
                    if totals[dbcr] > amount:
                        raise ParseException(block[0], '%ss (%s) exceed amount (%s)' % (desc, totals[dbcr], amount))
                    elif totals[dbcr] < amount:
                        if entries_noamt[dbcr] is not None:
                            entries_noamt[dbcr]['amount'] = (amount - totals[dbcr]) * sign
                            entries.append(entries_noamt[dbcr])
                        else:
                            raise ParseException(block[0], '%ss (%s) do not sum to amount (%s)' % (desc, totals[dbcr], amount))
                    elif entries_noamt[dbcr] is not None:
                        raise ParseException(entries_noamt[dbcr]['line'], 'nil entry; credits already sum to amount (%s)' % (amount,))
                for entry in entries:
                    del entry['line']
                kwargs['entries'] = entries
                self.transactions.append(Transaction(**kwargs))
            else:
                raise ParseException(tags['type'], 'unknown type %r' % (tags['type'].text,))
            for tag in used:
                if not used[tag]:
                    raise ParseException(tags[tag], 'spurious %r tag' % (tag,))

    @classmethod
    def _parse_date(cls, line):
        try:
            return datetime.datetime.strptime(line.text, '%d/%m/%Y').date()
        except ValueError:
            raise ParseException(line, 'invalid date %r' % line.text)

    @classmethod
    def _parse_money(cls, line):
        try:
            return abo.config.parse_money(line.text)
        except ValueError:
            raise ParseException(line, 'invalid amount %r' % line.text)

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
'transactions':r"""

>>> Journal(r'''
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food
... cr bank
... amt 10.00
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
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
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
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
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
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
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
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
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
ParseException: StringIO, 3: spurious 'due' tag

>>> Journal(r'''
... %default due 21/3/2013
... type transaction
... date 21/2/2013
... who Somebody
... what something
... db food 10
... cr bank
... ''').transactions #doctest: +NORMALIZE_WHITESPACE
[Transaction(date=datetime.date(2013, 2, 21),
    who='Somebody', what='something',
    entries=(Entry(account='food', amount=Money(-10.00, Currencies.AUD)),
             Entry(account='bank', amount=Money(10.00, Currencies.AUD))))]

""",
}

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
