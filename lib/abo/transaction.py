# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Transaction is an immutable object representing a single, indivisible item
in the journal.  The movements in a Transaction are represented by a list of
two or more Entry objects.  The debits and credits of all the Entries in a
Transaction must balance to zero, and no Entry can be for a zero amount.

>>> t1 = Transaction(date=1, who="Someone", what="something",
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
Transaction(date=1, who='Someone', what='something', entries=(Entry(account='a1', amount=-14.56), Entry(account='a2', amount=14.56, detail='else')))
>>> t2 = Transaction(date=2, who="Them", what="whatever", entries=t1.entries)
>>> t2.entries[0].transaction is t2
True
>>> t2.entries[1].description()
'Them; whatever, else'
>>>
"""

import abo.base

class Entry(abo.base.Base):
    """An Entry is an immutable object reprenting a single debit or credit to a
    single account.
    """

    def __init__(self, transaction, account=None, amount=None, detail=""):
        """Construct a new Entry object, given its account, amount (-ve for
        debit, +ve for credit), and optional descriptive detail.
        """
        assert account is not None, 'missing account'
        assert amount is not None, 'missing amount'
        assert amount != 0, 'zero amount'
        self.id = self._make_unique_id()
        self.transaction = transaction
        self.account = account
        self.amount = amount
        self.detail = detail

    def __repr__(self):
        r = []
        r.append(('account', self.account))
        r.append(('amount', self.amount))
        if self.detail:
            r.append(('detail', self.detail))
        return '%s(%s)' % (type(self).__name__, ', '.join('%s=%r' % i for i in r))

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

    def description(self):
        """Return the full description for this Entry, by appending its detail
        string to the description string of its Transaction, separated by a
        comma and space.
        """
        return ', '.join([s for s in (self.transaction.description(), self.detail) if s])


class Transaction(abo.base.Base):
    """A Transaction is an immutable object that has a date, an optional
    control date, "who" and "what" strings that together describe the
    transaction for humans, and a list of two or more Entries.
    """

    def __init__(self, date=None, cdate=None, who=None, what=None, entries=()):
        """Construct a new Transaction object, given its date, optional control
        date, description, and list of Entry objects.
        """
        assert date is not None, 'missing date'
        assert who is not None, 'missing who'
        assert what is not None, 'missing what'
        assert len(entries) >= 2, 'too few entries'
        self.id = self._make_unique_id()
        self.date = date
        self.cdate = cdate
        self.who = who
        self.what = what
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
        if self.cdate:
            r.append(('cdate', self.cdate))
        r.append(('who', self.who))
        r.append(('what', self.what))
        r.append(('entries', self.entries))
        return '%s(%s)' % (type(self).__name__, ', '.join('%s=%r' % i for i in r))

    def description(self):
        """Return the full description for this Transaction, by appending its
        who and what strings, separated by a semicolon and space.  The
        semicolon allows a description string to be split into who and what
        strings if needed.
        """
        return '; '.join([s for s in (self.who, self.what) if s])

__test__ = {
'accessors':"""
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':-14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':14.56}))
    >>> t.date
    1
    >>> t.cdate
    7
    >>> t.who
    'Someone'
    >>> t.what
    'something'
    >>> len(t.entries)
    2
    >>> t.entries[0].account
    'a1'
    >>> t.entries[0].amount
    -14.56
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
'errors':"""
    >>> t = Transaction(cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError: missing date
    >>> t = Transaction(date=1, cdate=7, what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError: missing who
    >>> t = Transaction(date=1, cdate=7, who="Someone", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError: missing what
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'},))
    Traceback (most recent call last):
    AssertionError: too few entries
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError: entries sum to zero
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError: missing account
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}, \\
    ...                  {'account':'a3', 'amount':0.00}))
    Traceback (most recent call last):
    AssertionError: zero amount
""",
}

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
