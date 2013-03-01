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
        for line in lines:
            line = line.rstrip('\n')
            if line:
                words = line.split(None, 2)
                if words[0] == '#line' and len(words) > 1 and words[1].isdigit():
                    lnum = int(words[1])
                elif words[0].startswith('#'):
                    lnum += 1
                else:
                    lnum += 1
                    block.append((lnum, line))
            elif block:
                blocks.append(block)
                block = []
        if block:
            blocks.append(block)
        optional = set(['due', 'amt'])
        template = {
            'type': None,
            'date': None,
            'due': None,
            'who': None,
            'what': None,
            'db': [],
            'cr': [],
            'amt': None,
        }
        defaults = copy.deepcopy(template)
        for block in blocks:
            tags = copy.deepcopy(template)
            empty = True
            for lnum, line in block:
                words = line.split(None, 1)
                if words[0] == '%default':
                    try:
                        tag, text = words[1].split(None, 1)
                    except ValueError, e:
                        raise ParseException(source_file, lnum, 'syntax error, expecting "%default <tag> <text>"')
                    if tag not in template:
                        raise ParseException(source_file, lnum, 'invalid %%default tag %r' % tag)
                    if not text:
                        defaults[tag] = template[tag]
                    elif type(template[tag]) is list:
                        defaults[tag] = [(lnum, text)]
                    else:
                        defaults[tag] = (lnum, text)
                    continue
                if words[0].startswith('%'):
                    continue
                try:
                    tag, text = line.split(None, 1)
                except ValueError, e:
                    raise ParseException(source_file, lnum, 'syntax error, expecting "<tag> <text>"')
                if tag not in tags:
                    raise ParseException(source_file, lnum, 'invalid tag %r' % tag)
                if type(tags[tag]) is list:
                    tags[tag].append((lnum, text))
                elif tags[tag] is None:
                    tags[tag] = (lnum, text)
                else:
                    raise ParseException(source_file, lnum, 'duplicate tag %r' % tag)
                empty = False
            if empty:
                continue
            for tag in tags:
                if not tags[tag]:
                    if defaults.get(tag):
                        tags[tag] = defaults[tag]
                    elif tag not in optional:
                        raise ParseException(source_file, block[0][0], 'missing tag %r', tag)
            kwargs = {}
            try:
                kwargs['date'] = datetime.datetime.strptime(tags['date'][1], '%d/%m/%Y').date()
            except ValueError:
                raise ParseException(source_file, tags['date'][0], 'invalid date %r' % tags['date'][1])
            if tags['due']:
                try:
                    kwargs['cdate'] = datetime.datetime.strptime(tags['due'][1], '%d/%m/%Y').date()
                except ValueError:
                    raise ParseException(source_file, tags['due'][0], 'invalid due date %r' % tags['due'][1])
            kwargs['who'] = tags['who'][1]
            kwargs['what'] = tags['what'][1]
            if tags['amt']:
                try:
                    amount = abo.config.parse_money(tags['amt'][1])
                except ValueError:
                    raise ParseException(source_file, tags['amt'][0], 'invalid amount %r' % tags['amt'][1])
            else:
                amount = None
            if tags['type'][1] == 'transaction':
                entries = []
                totals = {'db': 0, 'cr': 0}
                entries_noamt = {'db': None, 'cr': None}
                for dbcr, sign in (('db', -1), ('cr', 1)):
                    for lnum, ent in tags[dbcr]:
                        words = ent.split(None, 2)
                        entry = {}
                        money = None
                        entry['account'] = words.pop(0)
                        if words and self.appears_money(words[0]):
                            try:
                                money = abo.config.parse_money(words.pop(0))
                            except ValueError:
                                raise ParseException(source_file, lnum, 'invalid amount %r' % words[1])
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
                            raise ParseException(source_file, lnum, '%s missing amount' % (dbcr,))
                if amount is None and entries:
                    amount = max(totals.values())
                for dbcr, sign, desc in (('db', -1, 'debit'), ('cr', 1, 'credit')):
                    if totals[dbcr] > amount:
                        raise ParseException(source_file, lnum, '%ss (%s) exceed amount (%s)' % (desc, totals[dbcr], amount))
                    elif totals[dbcr] < amount:
                        if entries_noamt[dbcr] is not None:
                            entries_noamt[dbcr]['amount'] = (amount - totals[dbcr]) * sign
                            entries.append(entries_noamt[dbcr])
                        else:
                            raise ParseException(source_file, lnum, '%ss (%s) do not sum to amount (%s)' % (desc, totals[dbcr], amount))
                    elif entries_noamt[dbcr] is not None:
                        raise ParseException(source_file, lnum, 'nil entry; credits already sum to amount (%s)' % (amount,))
                kwargs['entries'] = entries
                self.transactions.append(Transaction(**kwargs))
            else:
                raise ParseException(source_file, tags['type'][0], 'unknown type %r' % (tags['type'][1],))

    _regex_amount = re.compile(r'\d*\.\d+|\d+')

    @classmethod
    def appears_money(cls, text):
        return cls._regex_amount.search(text) is not None

class ParseException(Exception):

    def __init__(self, source_file, line_number, message):
        super(ParseException, self).__init__('%s, %u: %s' % (getattr(source_file, 'name', type(source_file).__name__), line_number, message))

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
... #line 20 wah
... what whatever
... db
... ''') #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
ParseException: StringIO, 22: syntax error, expecting "<tag> <text>"

""",
}

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
