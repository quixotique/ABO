# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Journal is a source of Transactions parsed from a text file.

>>> j1 = Journal(_test_j1)
>>> for t in j1.transactions: t
Transaction(date=datetime.date(2013, 2, 21), who='Somebody', what='something', entries=(Entry(account='food', amount=Money(-10.00, Currencies.AUD)), Entry(account='bank', amount=Money(10.00, Currencies.AUD))))
Transaction(date=datetime.date(2013, 2, 22), who='Somebody Else', what='another thing', entries=(Entry(account='food', amount=Money(-7.00, Currencies.AUD)), Entry(account='drink', amount=Money(-3.00, Currencies.AUD)), Entry(account='bank', amount=Money(10.00, Currencies.AUD))))
>>>
"""

import StringIO
_test_j1 = StringIO.StringIO(r'''

type transaction
date 21/2/2013
who Somebody
what something
db food
cr bank
amt 10.00

type transaction
date 22/2/2013
who Somebody Else
what another thing
db food 7
db drink 3
cr bank 10

''')
_test_j1.name = 'StringIO'

import datetime
from abo.transaction import Transaction
import abo.config

class Journal(object):

    def __init__(self, source_file):
        self.transactions = []
        self._parse(source_file)

    def _parse(self, source_file):
        lines = list(source_file)
        blocks = []
        block = []
        for lnum, line in enumerate(lines, 1):
            line = line.rstrip('\n')
            if line:
                block.append((lnum, line))
            elif block:
                blocks.append(block)
                block = []
        if block:
            blocks.append(block)
        for block in blocks:
            optional = set(['due', 'amt'])
            tags= {
                'type': None,
                'date': None,
                'due': None,
                'who': None,
                'what': None,
                'db': [],
                'cr': [],
                'amt': None,
            }
            for lnum, line in block:
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
            for tag in tags:
                if tag not in optional and not tags[tag]:
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
                for dbcr, sign in (('db', -1), ('cr', 1)):
                    for lnum, ent in tags[dbcr]:
                        words = ent.split(None, 2)
                        dbcr_amount = amount
                        if len(words) > 1:
                            try:
                                dbcr_amount = abo.config.parse_money(words[1])
                            except ValueError:
                                raise ParseException(source_file, lnum, 'invalid amount %r' % words[1])
                        if dbcr_amount is None:
                            raise ParseException(source_file, lnum, 'missing amount')
                        entry = {'account': words[0], 'amount': dbcr_amount * sign}
                        if len(words) > 2:
                            entry['detail'] = words[2]
                        entries.append(entry)
                kwargs['entries'] = entries
                self.transactions.append(Transaction(**kwargs))
            else:
                raise ParseException(source_file, tags['type'][0], 'unknown type %r', tags['type'][1])

class ParseException(Exception):

    def __init__(self, source_file, line_number, message):
        super(ParseException, self).__init__('%s, %u: %s' % (getattr(source_file, 'name', type(source_file).__name__), line_number, message))

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
