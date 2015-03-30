# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Transaction is an immutable object representing a single, indivisible item
in the journal.  The movements in a Transaction are represented by a list of
two or more Entry objects.  The debits and credits of all the Entries in a
Transaction must balance to zero, and no Entry can be for a zero amount.

>>> t1 = Transaction(date=1, edate=3, who="Someone", what="something",
...         entries=({'account':'a2', 'amount':14.56, 'detail':'else'},
...                  {'account':'a1', 'amount':-14.56}))
>>> t1.description()
'Someone; something'
>>> t1.entries[0].transaction is t1
True
>>> t1.entries[0].account
'a1'
>>> t1.entries[0].amount
-14.56
>>> t1.entries[1].description()
'Someone; something, else'
>>> t1
Transaction(date=1, edate=3, who='Someone', what='something', entries=(Entry(account='a1', amount=-14.56), Entry(account='a2', amount=14.56, detail='else')))
>>> t2 = Transaction(date=2, edate=4, who="Them", what="whatever", entries=t1.entries)
>>> t2.entries[0].transaction is t2
True
>>> t2.entries[1].description()
'Them; whatever, else'
>>>
"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.transaction
    doctest.testmod(abo.transaction)

import re
import datetime
from itertools import chain
import abo.base

def sign(number):
    return -1 if number < 0 else 1 if number > 0 else 0

class Entry(abo.base.Base):
    """An Entry is an immutable object reprenting a single debit or credit to a
    single account.
    """

    def __init__(self, transaction, account=None, amount=None, cdate=None, detail=""):
        """Construct a new Entry object, given its account, amount (-ve for
        debit, +ve for credit), and optional descriptive detail.
        """
        assert account is not None, 'missing account'
        assert amount is not None, 'missing amount'
        assert amount != 0, 'zero amount'
        self.id = self._make_unique_id()
        self.transaction = transaction
        self.account = str(account)
        self.amount = amount
        self.cdate = cdate
        self.detail = str(detail) if detail is not None else None

    def __repr__(self):
        r = []
        r.append(('account', self.account))
        r.append(('amount', self.amount))
        if self.cdate:
            r.append(('cdate', self.cdate))
        if self.detail:
            r.append(('detail', self.detail))
        return '%s(%s)' % (type(self).__name__, ', '.join('%s=%r' % i for i in r))

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if not isinstance(other, Entry):
            return NotImplemented
        return (self.account == other.account
            and self.amount == other.amount
            and self.cdate == other.cdate
            and self.detail == other.detail)

    def __ne__(self, other):
        if not isinstance(other, Entry):
            return NotImplemented
        return not (self == other)

    def _attach(self, transaction):
        """Return an Entry object that is identical to this one, attached to
        the given Transaction object.  Since Entry objects are immutable, if
        this Entry object is already attached to the given Transaction, then
        this method just returns a reference to the object itself.  Otherwise,
        this method returns a copy of the object, attached to the given
        transction, and with a new id.
        """
        if self.transaction is transaction:
            return self
        return Entry(transaction, account=self.account, amount=self.amount, detail=self.detail)

    def sign(self):
        return sign(self.amount)

    def description(self):
        """Return the full description for this Entry, by appending its detail
        string to the description string of its Transaction, separated by a
        comma and space.
        """
        return ', '.join([s for s in (self.transaction.description(), self.detail) if s])

    def others(self):
        """Return an iterator over all other Entries in this Entry's transaction.
        """
        assert self.transaction
        for e in self.transaction.entries:
            if e is not self:
                yield e

    def replace(self, amount=None):
        """Return a copy of this Entry with new attributes and no transaction.
        """
        return type(self)(None, account=self.account, amount= self.amount if amount is None else amount, detail=self.detail)

    def replace_with(self, entry, date=None, split=False):
        """Replace this Entry in its transaction with another Entry.  The new
        Entry's amount must have the same sign and must not exceed this entry's
        amount.
         - If the amounts are equal and 'split' is False, a new Transaction
           object is created which contains the new Entry.  If the new Entry
           was already attached to another Transaction, then returns a copy of
           the new Entry attached to the new Transaction.
         - If the amounts are equal and 'split' is True, then two new
           Transactions are created, the first containing the new entry (or a
           copy) and the second containing all other entries with the same
           sign.  All remaining Entries of the opposite sign are divided
           proportionally between the two transactions.  Returns the two
           entries.  If there are no other Entries with the same sign, then
           returns None for the second Entry.
         - If the amount of the new Entry is less, then two new Transactions
           are created, the first containing the new Entry (or a copy) and the
           second containing a copy of this Entry with the amount reduced to
           the remainder.  All remaining Entries are divided proportionally
           between the two transactions.  Returns the two entries.
        >>> t1 = Transaction(date=1, who="Someone", what="something",
        ...         entries=({'account':'a1', 'amount':1476, 'detail':'else'},
        ...                  {'account':'a2', 'amount':500, 'detail':'blue'},
        ...                  {'account':'a3', 'amount':-1020, 'detail': 'old'},
        ...                  {'account':'a4', 'amount':-956}))
        >>> e = t1.entries[0].replace_with(Entry(None, account='a5', amount=-1000, detail='new'))
        >>> e #doctest: +NORMALIZE_WHITESPACE
        (Entry(account='a5', amount=-1000, detail='new'), Entry(account='a3', amount=-20, detail='old'))
        >>> e[0].transaction #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a5', amount=-1000, detail='new'),
                             Entry(account='a2', amount=253, detail='blue'),
                             Entry(account='a1', amount=747, detail='else')))
        >>> e[1].transaction #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a4', amount=-956),
                             Entry(account='a3', amount=-20, detail='old'),
                             Entry(account='a2', amount=247, detail='blue'),
                             Entry(account='a1', amount=729, detail='else')))
        >>> e = t1.entries[2].replace_with(Entry(None, account='a5', amount=500, detail='new'))
        >>> e #doctest: +NORMALIZE_WHITESPACE
        (Entry(account='a5', amount=500, detail='new'), None)
        >>> e[0].transaction #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a3', amount=-1020, detail='old'),
                             Entry(account='a4', amount=-956),
                             Entry(account='a5', amount=500, detail='new'),
                             Entry(account='a1', amount=1476, detail='else')))
        >>> e = t1.entries[2].replace_with(Entry(None, account='a5', amount=500, detail='new'), split=True)
        >>> e #doctest: +NORMALIZE_WHITESPACE
        (Entry(account='a5', amount=500, detail='new'), Entry(account='a1', amount=1476, detail='else'))
        >>> e[0].transaction #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a3', amount=-259, detail='old'),
                             Entry(account='a4', amount=-241),
                             Entry(account='a5', amount=500, detail='new')))
        >>> e[1].transaction #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a3', amount=-761, detail='old'),
                             Entry(account='a4', amount=-715),
                             Entry(account='a1', amount=1476, detail='else')))
        """
        assert abs(entry.amount) > 0
        assert sign(entry.amount) == self.sign()
        assert abs(entry.amount) <= abs(self.amount)
        assert self.transaction is not None
        orig_entries = set(self.transaction.entries)
        orig_entries.remove(self)
        if self.amount == entry.amount and not split:
            orig_entries.add(entry)
            t1 = self.transaction.replace(entries= orig_entries, date=date)
            t2 = None
        else:
            entries1 = [entry]
            if self.amount != entry.amount:
                entry2 = self.replace(amount= self.amount - entry.amount)
                entries2 = [entry2]
            else:
                entry2 = None
                entries2 = []
            for e in list(orig_entries):
                if e.sign() == self.sign():
                    orig_entries.remove(e)
                    e = e.replace()
                    entries2.append(e)
                    if (    entry2 is None
                        or  (entry2.account != entry.account and e.account == entry.account)
                        or  abs(e.amount) > abs(entry2.amount)
                    ):
                        entry2 = entries2[0]
            assert orig_entries
            prop = float(abs(entry.amount)) / float(self.transaction.amount())
            orig_entries = sorted(orig_entries, key=lambda e: abs(e.amount))
            total = 0
            while orig_entries:
                e = orig_entries.pop(0)
                assert e.sign() != self.sign()
                if orig_entries:
                    amt = prop * e.amount
                    if type(amt) is not type(e.amount):
                        amt = type(e.amount)(prop * e.amount)
                    total += amt
                    assert abs(total) < abs(entry.amount)
                else:
                    amt = -entry.amount - total
                assert type(amt) is type(e.amount), 'type(amt)=%r type(e.amount)=%r' % (type(amt), type(e.amount))
                if amt:
                    entries1.append(e.replace(amount= amt))
                if amt != e.amount:
                    entries2.append(e.replace(amount= e.amount - amt))
            t1 = self.transaction.replace(entries= entries1, date=date)
            t2 = self.transaction.replace(entries= entries2) if entries2 else None
        e1 = t1.entries[t1.entries.index(entry)]
        e2 = t2.entries[t2.entries.index(entry2)] if t2 is not None else None
        return e1, e2

class Transaction(abo.base.Base):
    """A Transaction is an immutable object that has a date, an optional
    control date, "who" and "what" strings that together describe the
    transaction for humans, and a list of two or more Entries.
    """

    def __init__(self, date=None, edate=None, who=None, what=None, is_projection=False, entries=()):
        """Construct a new Transaction object, given its date, optional control
        date, description, and list of Entry objects.
        """
        assert date is not None, 'missing date'
        assert len(entries) >= 2, 'too few entries'
        self.id = self._make_unique_id()
        self.date = date
        self.edate = edate if edate is not None else date
        self.who = who
        self.what = self._expand(what, date=date) if what else what
        self.is_projection = is_projection
        # Construct member Entry objects and ensure that they sum to zero.
        ents = []
        bal = 0
        for e in entries:
            if isinstance(e, Entry):
                ents.append(e._attach(self))
            else:
                e = Entry(self, **e)
                ents.append(e)
            bal += e.amount
        assert bal == 0, 'entries sum to zero'
        self.entries = tuple(sorted(ents, key=lambda e: (e.amount, e.account, e.detail)))

    def __repr__(self):
        r = []
        r.append(('date', self.date))
        if self.edate != self.date:
            r.append(('edate', self.edate))
        if self.who:
            r.append(('who', self.who))
        if self.what:
            r.append(('what', self.what))
        r.append(('entries', self.entries))
        return '%s(%s)' % (type(self).__name__, ', '.join('%s=%r' % i for i in r))

    def amount(self):
        """Return the absolute (positive) sum of all credits in this transaction.
        """
        return sum(e.amount for e in self.entries if e.amount > 0)

    def description(self):
        """Return the full description for this Transaction, by appending its
        who and what strings, separated by a semicolon and space.  The
        semicolon allows a description string to be split into who and what
        strings if needed.
        """
        return '; '.join(s for s in (self.who, self.what) if s and s.strip())

    def replace(self, date=None, entries=None):
        """Return a copy of this Transaction with new attributes.
        """
        return type(self)(
                date= self.date if date is None else date,
                who= self.who,
                what= self.what,
                entries= self.entries if entries is None else entries
            )

    def split(self, account, amount):
        """Split this Transaction into two, by splitting all of its Entries on
        a given account into two sets, the first set summing to a given amount
        and the second being the remainder.
        The given amount must have the same sign as the sum of the account's
        Entries and must not exceed this entry's amount.
        The Entries are split by dividing each proportionately to create two
        sets each having the same number of entries (or fewer if any
        proportional amounts round to zero).
        >>> t = Transaction(date=1, who="Someone", what="something",
        ...         entries=({'account':'a1', 'amount':1476, 'detail':'else'},
        ...                  {'account':'a1', 'amount':500, 'detail':'blue'},
        ...                  {'account':'a2', 'amount':-1020, 'detail': 'old'},
        ...                  {'account':'a2', 'amount':-956}))
        >>> t1, t2 = t.split('a1', 1000)
        >>> t1 #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a2', amount=-517, detail='old'),
                             Entry(account='a2', amount=-483),
                             Entry(account='a1', amount=253, detail='blue'),
                             Entry(account='a1', amount=747, detail='else')))
        >>> t2 #doctest: +NORMALIZE_WHITESPACE
        Transaction(date=1, who='Someone', what='something',
                    entries=(Entry(account='a2', amount=-503, detail='old'),
                             Entry(account='a2', amount=-473),
                             Entry(account='a1', amount=247, detail='blue'),
                             Entry(account='a1', amount=729, detail='else')))
        """
        entries = list(self.entries)
        assert entries
        aentries = [e for e in self.entries if e.account == account]
        oentries = [e for e in self.entries if e.account != account]
        total = sum(e.amount for e in aentries)
        assert amount != 0
        assert sign(amount) == sign(total)
        assert abs(amount) <= abs(total)
        if amount == total:
            return self, None
        entries1, entries2 = _divide_entries(aentries, amount)
        other1, other2 = _divide_entries(oentries, -amount)
        assert sum(e.amount for e in chain(entries1, entries2, other1, other2)) == 0
        assert sum(e.amount for e in chain(entries1, entries2) if e.account == account) == total
        assert sum(e.amount for e in entries1 if e.account == account) == amount
        assert sum(e.amount for e in other1 if e.account != account) == -amount, 'other1=%r amount=%r' % (other1, amount)
        return self.replace(entries= entries1 + other1), self.replace(entries= entries2 + other2)

    _regex_expand_field = re.compile(r'%{(\w+)([+-]\d+)?}')

    def _expand(self, text, date):
        def repl(m):
            if m.group(1) == 'date':
                d = date
                if m.group(2):
                    d += datetime.timedelta(int(m.group(2)))
                return d.strftime(r'%-d-%b-%Y')
            return text
        return self._regex_expand_field.sub(repl, text)

def _divide_entries(entries, amount):
    entries = sorted(entries, key=lambda e: (abs(e.amount), e.account))
    totale = sum(e.amount for e in entries)
    total1 = amount
    entries1 = []
    entries2 = []
    while len(entries) > 1:
        assert abs(total1) < abs(totale)
        ratio = float(abs(total1)) / float(abs(totale))
        assert 0 <= ratio <= 1.0
        e = entries.pop(0)
        amt = e.amount * ratio
        if type(amt) is not type(e.amount):
            amt = type(e.amount)(amt)
        assert abs(amt) <= abs(e.amount)
        if amt != 0:
            entries1.append(e.replace(amount= amt))
        if amt != e.amount:
            entries2.append(e.replace(amount= e.amount - amt))
        total1 -= amt
        totale -= e.amount
    assert len(entries) == 1
    e = entries[0]
    assert totale == e.amount
    if total1:
        entries1.append(e.replace(amount= total1))
    if total1 != e.amount:
        entries2.append(e.replace(amount= e.amount - total1))
    return entries1, entries2


__test__ = {
'accessors':"""
    >>> t = Transaction(date=1, who="Someone", what="something", is_projection=True, \\
    ...         entries=({'account':'a1', 'amount':-14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':14.56, 'cdate': 7}))
    >>> t.date
    1
    >>> t.who
    'Someone'
    >>> t.what
    'something'
    >>> t.is_projection
    True
    >>> len(t.entries)
    2
    >>> t.amount()
    14.56
    >>> t.entries[0].account
    'a1'
    >>> t.entries[0].amount
    -14.56
    >>> t.entries[0].cdate
    >>> t.entries[0].detail
    'else'
    >>> t.entries[0].description()
    'Someone; something, else'
    >>> t.entries[0].transaction is t
    True
    >>> t.entries[1].account
    'a2'
    >>> t.entries[1].amount
    14.56
    >>> t.entries[1].cdate
    7
    >>> t.entries[1].detail
    ''
    >>> t.entries[1].description()
    'Someone; something'
    >>> t.id == t.entries[0].id
    False
    >>> t.id == t.entries[1].id
    False
    >>> t.entries[0].id == t.entries[1].id
    False
""",
'replace':"""
    >>> t = Transaction(date=1, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':-14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':14.56, 'cdate': 7}))
    >>> t.entries[0].replace(amount=-22.01)
    Entry(account='a1', amount=-22.01, detail='else')
    >>> t.entries[0]
    Entry(account='a1', amount=-14.56, detail='else')
""",
'errors':"""
    >>> t = Transaction(who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError: missing date
    >>> t = Transaction(date=1, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'},))
    Traceback (most recent call last):
    AssertionError: too few entries
    >>> t = Transaction(date=1, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError: entries sum to zero
    >>> t = Transaction(date=1, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError: missing account
    >>> t = Transaction(date=1, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}, \\
    ...                  {'account':'a3', 'amount':0.00}))
    Traceback (most recent call last):
    AssertionError: zero amount
""",
}
