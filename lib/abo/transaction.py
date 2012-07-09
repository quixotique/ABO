"""A Transaction is an immutable object representing a single, indivisible item
in the journal.  The movements in a Transaction are represented by a list of
two or more Entry objects.  The debits and credits of all the Entries in a
Transaction must balance to zero, and no Entry can be for a zero amount.

>>> t1 = Transaction(date=1, who="Someone", what="something", \\
...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
...                  {'account':'a2', 'amount':-14.56}))
>>> t1.description()
'Someone; something'
>>> t1.entry(0).transaction() is t1
True
>>> t1.entry(0).account()
'a1'
>>> t1.entry(0).amount()
14.56
>>> t1.entry(0).description()
'Someone; something, else'
>>> t2 = Transaction(date=2, who="Them", what="whatever", \\
...                  entries=t1.entries())
>>> t2.entry(0).transaction() is t2
True
>>> t2.entry(0).description()
'Them; whatever, else'
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
        assert account is not None
        assert amount is not None and amount != 0
        self._id = self._make_unique_id()
        self._transaction = transaction
        self._account = account
        self._amount = amount
        self._detail = detail

    def _attach(self, transaction):
        """Return an Entry object that is identical to this one, attached to
        the given Transaction object.  Since Entry objects are immutable, if
        this Entry object is already attached to the given Transaction, then
        this method just returns a reference to the object itself.  Otherwise,
        this method returns a copy of the object, attached to the given
        transction, and with a new id.
        """
        if self._transaction is transaction:
            return self
        return Entry(transaction, account=self._account, amount=self._amount, detail=self._detail)

    def id(self):
        """Return the unique ID number of this entry.  See abo.base for further
        information about uinque IDs.
        """
        return self._id

    def transaction(self):
        """Return a reference to the Transaction object to which this Entry
        object belongs.  Every Entry object belongs to exactly one Transaction
        object.
        """
        return self._transaction

    def account(self):
        """Return a reference to the Account object for the account which this
        Entry credits or debits.
        """
        return self._account

    def amount(self):
        """Return the amount that this Entry credits (+ve) or debits (-ve) to
        the account.
        """
        return self._amount

    def detail(self):
        """Return a human-readable string description that distinguishes this
        Entry from other Entries in the same Transaction.  See the
        description() method for how this string is normally combined with the
        Transaction's description string.
        """
        return self._detail

    def description(self):
        """Return the full description for this Entry, by appending its
        detail() string to the description string of its Transaction, separated
        by a comma and space.
        """
        return ', '.join([s for s in (self.transaction().description(), self.detail()) if len(s)])


class Transaction(abo.base.Base):
    """A Transaction is an immutable object that has a date, an optional
    control date, "who" and "what" strings that together describe the
    transaction for humans, and a list of two or more Entries.
    """

    def __init__(self, date=None, cdate=None, who=None, what=None, entries=()):
        """Construct a new Transaction object, given its date, optional control
        date, description, and list of Entry objects.
        """
        assert date is not None
        assert who is not None
        assert what is not None
        assert len(entries) >= 2
        self._id = self._make_unique_id()
        self._date = date
        self._cdate = cdate
        self._who = who
        self._what = what
        # Construct member Entry objects and ensure that they sum to zero.
        ents = []
        bal = self.make_money(0)
        for e in entries:
            if isinstance(e, Entry):
                ents.append(e._attach(self))
            else:
                e = Entry(self, **e)
                ents.append(e)
            bal += e.amount()
        assert bal == 0
        self._entries = tuple(ents)
        # Check that transaction is valid.
        self._validate_transaction(self)

    def id(self):
        """Return the unique ID number of this transaction.  See abo.base for
        further information about uinque IDs.
        """
        return self._id

    def date(self):
        """Return the Date object for this Transaction.
        """
        return self._date

    def cdate(self):
        """Return the "control" Date object for this Transaction.  This is
        typically used for the due date of an invoice or bill.  It could also
        be used for the clearing date of a deposited cheque or the redeemed
        date of a paid out cheque.
        """
        return self._cdate

    def who(self):
        """Return the "who" description for this Transaction.  This typically
        names the company or individual in a bill, receipt, payment, or
        incoming.  Often, the "who" string is identical to or at least closely
        resembles the name of the account payable or receivable associated with
        a bill or invoice.
        """
        return self._who

    def what(self):
        """Return the "what" description for this Transaction.  This is mandatory,
        and gives the reason for the Transaction.
        """
        return self._what

    def description(self):
        """Return the full description for this Transaction, by appending its
        who() and what() strings, separated by a semicolon and space.  The
        semicolon allows a description string to be split into who and what
        strings if needed.
        """
        return '; '.join([s for s in (self.who(), self.what()) if len(s)])

    def entries(self):
        """Return a tuple of all the Entry objects in this Transaction.
        """
        return self._entries

    def entry(self, i):
        """Return the i'th Entry object in this Transaction.  Shorthand for
        entries()[i], to help make code more readable.
        """
        return self._entries[i]


__test__ = {
'accessors':"""
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    >>> t.date()
    1
    >>> t.cdate()
    7
    >>> t.who()
    'Someone'
    >>> t.what()
    'something'
    >>> len(t.entries())
    2
    >>> t.entry(0).account()
    'a1'
    >>> t.entry(0).amount()
    14.56
    >>> t.entry(0).detail()
    'else'
    >>> t.entry(0).description()
    'Someone; something, else'
    >>> t.entry(0).transaction() is t
    True
    >>> t.entry(1).account()
    'a2'
    >>> t.entry(1).amount()
    -14.56
    >>> t.entry(1).detail()
    ''
    >>> t.entry(1).description()
    'Someone; something'
    >>> t.id() == t.entry(0).id()
    False
    >>> t.id() == t.entry(1).id()
    False
    >>> t.entry(0).id() == t.entry(1).id()
    False
""",
'errors':"""
    >>> t = Transaction(cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, who="Someone", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'},))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'amount':-14.55}))
    Traceback (most recent call last):
    AssertionError
    >>> t = Transaction(date=1, cdate=7, who="Someone", what="something", \\
    ...         entries=({'account':'a1', 'amount':14.56, 'detail':'else'}, \\
    ...                  {'account':'a2', 'amount':-14.56}, \\
    ...                  {'account':'a3', 'amount':0.00}))
    Traceback (most recent call last):
    AssertionError
""",
}

def _test():
    import doctest, abo.transaction
    return doctest.testmod(abo.transaction)

if __name__ == "__main__":
    _test()
