# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Money object represents an exact amount of a single currency.
"""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import abo.money
    import doctest
    doctest.testmod(abo.money)

import logging
# Suppress error caused by duplicate numeric code in iso_15294.xml
logging.getLogger('pycountry.db').setLevel(logging.CRITICAL)
import pycountry
import re
import decimal

class RegistryError(Exception):
    pass

class CurrencyMismatch(Exception):
    pass

class Currency(object):

    r"""
    Currency objects can be pickled and unpickled using protocol 2:

        >>> import pickle
        >>> import abo.money
        >>> pickle.loads(pickle.dumps(Currency.AUD, 2))
        Currency.AUD
        >>> pickle.loads(pickle.dumps(Currency.AUD, 2)) is Currency.AUD
        True
    """

    def __new__(cls, code, local_frac_digits=0, local_symbol=None, local_symbol_precedes=False, local_symbol_separated_by_space=False):
        currency = pycountry.currencies.get(alpha_3=code)
        if not currency:
            raise ValueError('invalid ISO 4217 currency code: %r' % (code,))
        code = str(code)
        singleton = getattr(cls, code, None)
        if singleton:
            assert singleton.code == code
            if (    singleton.local_frac_digits == local_frac_digits
                and singleton.local_symbol == local_symbol
                and singleton.local_symbol_precedes == local_symbol_precedes
                and singleton.local_symbol_separated_by_space == local_symbol_separated_by_space):
                return singleton
        self = super(Currency, cls).__new__(cls)
        self.code = code
        self.local_frac_digits = local_frac_digits
        self.local_symbol = local_symbol
        self.local_symbol_precedes = local_symbol_precedes
        self.local_symbol_separated_by_space = local_symbol_separated_by_space
        self.decimal_context = decimal.Context(
                prec= 15,
                rounding= decimal.ROUND_HALF_UP,
                traps= [decimal.DivisionByZero, decimal.InvalidOperation, decimal.Inexact])
        self.float_context = self.decimal_context.copy()
        self.float_context.rounding = decimal.ROUND_DOWN
        self.float_context.traps[decimal.Inexact] = False
        self.zero = decimal.Decimal(10, context=self.decimal_context) ** -self.local_frac_digits
        return self

    def __getnewargs__(self):
        r'''Pickle protocol 2 support.  Return a tuple of args that will be
        passed to __new__() when unpickled.
        '''
        return self.code, self.local_frac_digits, self.local_symbol, self.local_symbol_precedes, self.local_symbol_separated_by_space

    def __setstate__(self, state):
        r'''Catch an unpickling by a protocol that does not support
        __getnewargs__()/__new__().  If it does, then __new__() has already
        been called, so we check that it has produced the correct result.
        '''
        try:
            assert self.code == state['code']
        except (AttributeError, AssertionError):
            raise pickle.UnpicklingError(
                    '%s.enum does not support this protocol' % enum.__module__)
        assert self is Currency.__dict__.get(self.code)

    def register(self, registry=None):
        r'''Register this Currency object in the registry, to make it available globally.
        >>> Currency('USD')
        Currency('USD')
        >>> Currency('USD').register()
        Currency.USD
        >>> Currency('USD')
        Currency.USD
        >>> del Currency.USD
        >>> Currency('USD')
        Currency('USD')
        '''
        if registry is None:
            registry = self.__class__
        singleton = getattr(registry, self.code, None)
        if not singleton:
            setattr(registry, self.code, self)
            return self
        assert singleton.code == self.code
        if singleton == self:
            return singleton
        raise RegistryError("%s.%s already set" % (registry.__name__, singleton.code))

    def __hash__(self):
        return (hash(self.code) ^
                hash(self.local_frac_digits) ^
                hash(self.local_symbol) ^
                hash(self.local_symbol_precedes) ^
                hash(self.local_symbol_separated_by_space))

    def __eq__(self, other):
        if not isinstance(other, Currency):
            return NotImplemented
        return (other.code == self.code
            and other.local_frac_digits == self.local_frac_digits
            and other.local_symbol == self.local_symbol
            and other.local_symbol_precedes == self.local_symbol_precedes
            and other.local_symbol_separated_by_space == self.local_symbol_separated_by_space)

    def __ne__(self, other):
        if not isinstance(other, Currency):
            return NotImplemented
        return not self.__eq__(other)

    def __str__(self):
        return self.code

    def __repr__(self):
        singleton = getattr(self.__class__, self.code, None)
        if singleton is self:
            return '%s.%s' % (self.__class__.__name__, self.code)
        r = []
        for attr in ('local_frac_digits', 'local_symbol', 'local_symbol_precedes', 'local_symbol_separated_by_space'):
            value = getattr(self, attr)
            if value:
                r.append((attr, value))
        return '%s(%r%s)' % (type(self).__name__, self.code, ''.join(', %s=%r' % i for i in r))

    @staticmethod
    def extract_code(text):
        r'''Extract an ISO 4217 currency code prefix or suffix from the given text.
        >>> Currency.extract_code('AUD27.30')
        ('AUD', '27.30')
        >>> Currency.extract_code('AUD  5')
        ('AUD', '5')
        >>> Currency.extract_code('xxx AUD')
        ('AUD', 'xxx')
        >>> Currency.extract_code('$100.71')
        (None, '$100.71')
        >>> Currency.extract_code('$AUD 100.71')
        (None, '$AUD 100.71')
        '''
        currency = pycountry.currencies.get(alpha_3=text[:3])
        if currency is not None and currency.alpha_3 == text[:3]:
            return str(text[:3]), text[3:].lstrip()
        currency = pycountry.currencies.get(alpha_3=text[-3:])
        if currency is not None and currency.alpha_3 == text[-3:]:
            return str(text[-3:]), text[:-3].rstrip()
        return None, text

    @classmethod
    def extract_currency(cls, text):
        r'''Extract an ISO 4217 currency code prefix or suffix from the given text,
        and return the corresponding Currency object.
        >>> Currency.extract_currency('AUD 27.30')
        (Currency.AUD, '27.30')
        >>> Currency.extract_currency('1AUD')
        (Currency.AUD, '1')
        >>> Currency.extract_currency('USD 18.45')
        (None, 'USD 18.45')
        '''
        code, rest = cls.extract_code(text)
        if code:
            try:
                return getattr(cls, code), rest
            except AttributeError:
                pass
        return None, text

    _amount_regex = re.compile(r'(?P<sign>[+-]?)(?P<decimal>\b(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?|\.\d+)\b')

    @classmethod
    def parse_amount_currency(cls, text, default_currency=None):
        r'''Parse given text into a Decimal amount and a Currency object.
        >>> Currency.parse_amount_currency('123')
        Traceback (most recent call last):
        ValueError: missing currency code in '123'
        >>> Currency.parse_amount_currency('AUD 123')
        (Currency.AUD, Decimal('123'))
        >>> Currency.parse_amount_currency('AUD $-4,567')
        (Currency.AUD, Decimal('-4567'))
        >>> Currency.parse_amount_currency('AUD -$4,567')
        (Currency.AUD, Decimal('-4567'))
        >>> Currency.parse_amount_currency('AUD -$-4,567')
        Traceback (most recent call last):
        ValueError: invalid amount: '-$-4,567'
        >>> Currency.parse_amount_currency('AUD $-4,567.8')
        (Currency.AUD, Decimal('-4567.8'))
        >>> Currency.parse_amount_currency('AUD $+34,567.891')
        (Currency.AUD, Decimal('34567.891'))
        >>> Currency.parse_amount_currency('123AUD')
        (Currency.AUD, Decimal('123'))
        >>> Currency.parse_amount_currency('AUD 1.2.3')
        Traceback (most recent call last):
        ValueError: invalid amount: '1.2.3'
        >>> Currency.parse_amount_currency('123 USD')
        Traceback (most recent call last):
        ValueError: unknown currency 'USD' in '123 USD'
        '''
        code, amount = cls.extract_code(text)
        if code is None:
            if default_currency is None:
                raise ValueError('missing currency code in %r' % (text,))
            currency = default_currency
        else:
            currency = getattr(cls, code, None)
            if currency is None:
                raise ValueError('unknown currency %r in %r' % (code, text,))
        m = cls._amount_regex.search(amount)
        if not m:
            raise ValueError('invalid amount: %r' % (amount,))
        pre = amount[:m.start(0)]
        sign = m.group('sign')
        numeric = m.group('decimal').replace(',', '')
        post = amount[m.end(0):]
        if not sign and pre and pre[0] in '+-':
            sign = pre[0]
            pre = pre[1:]
        if currency.local_symbol:
            if currency.local_symbol_precedes:
                if pre.startswith(currency.local_symbol):
                    pre = pre[len(currency.local_symbol):].lstrip()
            else:
                if post.endswith(currency.local_symbol):
                    post = post[:-len(currency.local_symbol)].rstrip()
        if pre or post:
            raise ValueError('invalid amount: %r' % (amount,))
        return currency, decimal.Decimal(sign + numeric, context=currency.decimal_context)

    def parse_amount(self, text):
        r'''Parse given text as a decimal amount of this currency.
        >>> Currency.AUD.parse_amount('123')
        Decimal('123.00')
        >>> Currency.AUD.parse_amount('AUD 123')
        Decimal('123.00')
        >>> Currency.AUD.parse_amount('123 AUD')
        Decimal('123.00')
        >>> Currency.AUD.parse_amount('70.45')
        Decimal('70.45')
        >>> Currency.AUD.parse_amount('-$1,234,567.89')
        Decimal('-1234567.89')
        >>> Currency.AUD.parse_amount('+.05')
        Decimal('0.05')
        >>> Currency.AUD.parse_amount('123,456,789.10')
        Decimal('123456789.10')
        >>> Currency.AUD.parse_amount('AUD $-4,567.8')
        Traceback (most recent call last):
        ValueError: invalid literal for Currency.AUD: 'AUD $-4,567.8'
        >>> Currency.AUD.parse_amount('AUD $-4,567.80')
        Decimal('-4567.80')
        >>> Currency.AUD.parse_amount('70.456')
        Traceback (most recent call last):
        ValueError: invalid literal for Currency.AUD: '70.456'
        >>> Currency.AUD.parse_amount('EUR 123')
        Traceback (most recent call last):
        ValueError: currency code of 'EUR 123' should be 'AUD'
        >>> Currency.AUD.parse_amount('EUR 123')
        Traceback (most recent call last):
        ValueError: currency code of 'EUR 123' should be 'AUD'
        >>> Currency.AUD.parse_amount('AUD 1.2.3')
        Traceback (most recent call last):
        ValueError: invalid amount: '1.2.3'
        '''
        currency, amount = self.parse_amount_currency(text, default_currency=self)
        if currency is not self:
            raise ValueError('currency code of %r should be %r' % (text, self.code))
        try:
            exp = amount.as_tuple()[2]
            if exp == 0 or exp == -self.local_frac_digits:
                return self.decimal_context.quantize(amount, self.zero)
        except ValueError:
            pass
        raise ValueError('invalid literal for %r: %r' % (self, text))

    def quantize(self, amount):
        r'''Convert the given number into a Decimal value with the correct
        number of decimal places for this currency.  Raise ValueError if the
        given amount would have to be rounded (ie, has too many decimal
        places).
        >>> Currency.AUD.quantize(1)
        Decimal('1.00')
        >>> Currency.AUD.quantize(1.01)
        Decimal('1.01')
        >>> Currency.AUD.quantize(1.011)
        Traceback (most recent call last):
        ValueError: invalid literal for Currency.AUD: 1.011
        '''
        try:
            if isinstance(amount, float):
                tmp = self.float_context.create_decimal_from_float(amount)
            else:
                tmp = amount
            return self.decimal_context.quantize(tmp, self.zero)
        except decimal.Inexact:
            raise ValueError('invalid literal for %r: %r' % (self, amount))

    def format(self, amount, symbol=True, thousands=False, positive_sign='', positive_prefix='', positive_suffix='', negative_sign='-', negative_prefix='', negative_suffix=''):
        r'''Return a string representation of the Decimal amount with the
        currency symbol as prefix or suffix.
        >>> Currency.AUD.format(1)
        '$1.00'
        >>> Currency.AUD.format(-1)
        '$-1.00'
        >>> Currency.AUD.format(-100, negative_prefix='(', negative_sign='', negative_suffix=')')
        '($100.00)'
        >>> Currency.AUD.format(10000000)
        '$10000000.00'
        >>> Currency.AUD.format(10000000, thousands=True)
        '$10,000,000.00'
        >>> Currency.EUR.format(1) == '1.00 €'
        True
        '''
        amt = self.quantize(amount)
        fmt = '{0:,}' if thousands else '{0}'
        if symbol and self.local_symbol:
            fmt = '{4}{1}{2}{3}'+fmt+'{5}' if self.local_symbol_precedes else '{4}{3}'+fmt+'{2}{1}{5}'
        else:
            fmt = '{4}{3}'+fmt+'{5}'
        sep = ' ' if self.local_symbol_separated_by_space else ''
        return (fmt.format(amt, self.local_symbol, sep, positive_sign, positive_prefix, positive_suffix) if amt >= 0
                else fmt.format(-amt, self.local_symbol, sep, negative_sign, negative_prefix, negative_suffix))

    def parse_amount_money(self, text):
        r'''Parse given text into a Money object with this currency.
        >>> Currency.EUR.parse_amount_money('60001')
        Money.EUR(60001.00)
        '''
        return Money.from_text(text, currency=self)

    def money(self, amount):
        r'''Convert the given number into a Money object for this currency.
        Raise ValueError if the given amount would have to be rounded (ie, has
        too many decimal places.
        >>> Currency.AUD.money(1)
        Money.AUD(1.00)
        '''
        return self.money_factory(amount)

class Money(object):

    r'''Represents an exact amount (not fractional) of a given single currency.
    >>> class AUD(Money):
    ...    currency = Currency.AUD
    >>> AUD(140)
    AUD(140.00)
    >>> AUD(140.01)
    Traceback (most recent call last):
    ValueError: invalid literal for Currency.AUD: 140.01
    >>> AUD.from_text('140.01')
    Money.AUD(140.01)
    >>> AUD(70) + AUD(30)
    AUD(100.00)
    >>> AUD(70) + 30
    AUD(100.00)
    >>> 70 + AUD(30)
    AUD(100.00)
    >>> AUD(70) * 2
    AUD(140.00)
    >>> AUD(70) * 2.5
    AUD(175.00)
    >>> AUD(70) / 2
    AUD(35.00)
    '''

    def __init__(self, amount):
        assert isinstance(self.currency, Currency)
        self.amount = self.currency.quantize(amount)

    @classmethod
    def register(cls, currency=None):
        r'''Create a subclass of Money which is bound to a specific currency.
        >>> Money.register(Currency('HKD', 2))
        <class 'abo.money.HKD'>
        >>> Money.HKD(-6.99)
        Money.HKD(-6.99)
        >>> class Vatu(Money):
        ...    currency = Currency('VUV', 0, 'Vt', True, True)
        >>> Vatu(1200)
        Vatu(1200)
        >>> Vatu.register()
        <class 'abo.money.Vatu'>
        >>> Vatu(1200)
        Money.VUV(1200)
        '''
        if currency is not None:
            assert getattr(cls, 'currency', None) is None
            singleton = getattr(Money, currency.code, None)
            if singleton:
                assert singleton.currency is currency
                assert currency.money_factory is singleton
                return singleton
            singleton = type(currency.code, (Money,), dict(currency=currency))
        else:
            assert cls is not Money
            assert issubclass(cls, Money)
            currency = cls.currency
            singleton = getattr(Money, currency.code, None)
            if singleton:
                assert singleton is cls
                assert singleton.currency is currency
                assert currency.money_factory is singleton
                return singleton
            singleton = cls
        assert getattr(currency, 'money_factory', None) is None
        assert currency.code not in globals()
        setattr(Money, currency.code, singleton)
        globals()[currency.code] = singleton
        currency.money_factory = singleton
        return singleton

    @classmethod
    def from_text(cls, text, currency=None):
        r'''Parse a text string into a Money object.
        >>> Money.from_text('8071.51 AUD')
        Money.AUD(8071.51)
        >>> Money.from_text('-6.99 AUD')
        Money.AUD(-6.99)
        '''
        if currency is None:
            currency, number = Currency.extract_currency(text)
            if currency is None:
                currency = getattr(cls, 'currency')
            if currency is None:
                raise ValueError('invalid literal for %s.from_text(currency=None): %r' % (cls.__name__, text,))
        else:
            number = text
        return currency.money(currency.parse_amount(number))

    def format(self, **kwargs):
        return self.currency.format(self.amount, **kwargs)

    def __str__(self):
        return '%s %s' % (self.amount, self.currency)

    def __repr__(self):
        r'''
        >>> class Greenback(Money):
        ...     currency = Currency('USD')
        >>> Greenback(100)
        Greenback(100)
        >>> Greenback.register()
        <class 'abo.money.Greenback'>
        >>> Money.USD(100)
        Money.USD(100)
        >>> Greenback(100)
        Money.USD(100)
        '''
        if getattr(Money, self.currency.code, None) is self.__class__:
            classname = 'Money.%s' % (self.currency.code,)
        else:
            classname = type(self).__name__
        return '%s(%s)' % (classname, self.amount)

    def __bool__(self):
        return bool(self.amount)

    def __float__(self):
        return float(self.amount)

    def _unmoney(self, other, fmt):
        if isinstance(other, Money):
            if other.currency != self.currency:
                raise CurrencyMismatch(fmt.format(self, other))
            return other.amount
        return other

    def __hash__(self):
        return hash(self.currency) ^ hash(self.amount)

    def __eq__(self, other):
        return self.amount == self._unmoney(other, '{0} == {1}')

    def __ne__(self, other):
        return self.amount != self._unmoney(other, '{0} != {1}')

    def __lt__(self, other):
        return self.amount < self._unmoney(other, '{0} < {1}')

    def __le__(self, other):
        return self.amount <= self._unmoney(other, '{0} <= {1}')

    def __gt__(self, other):
        return self.amount > self._unmoney(other, '{0} > {1}')

    def __ge__(self, other):
        return self.amount >= self._unmoney(other, '{0} >= {1}')

    def __neg__(self):
        return type(self)(-self.amount)

    def __pos__(self):
        return type(self)(+self.amount)

    def __abs__(self):
        return type(self)(abs(self.amount))

    def __add__(self, other):
        return type(self)(self.amount + self._unmoney(other, '{0} + {1}'))

    def __sub__(self, other):
        return type(self)(self.amount - self._unmoney(other, '{0} - {1}'))

    def __radd__(self, other):
        return type(self)(self._unmoney(other, '{1} + {0}') + self.amount)

    def __rsub__(self, other):
        return type(self)(self._unmoney(other, '{1} - {0}') - self.amount)

    def __mul__(self, other):
        if isinstance(other, (float, int)):
            return type(self)(decimal.Decimal(float(self.amount) * other).quantize(self.currency.zero))
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (float, int)):
            return type(self)(self.amount / other)
        return NotImplemented

Money.register(Currency('AUD', 2, '$', True).register())
Money.register(Currency('EUR', 2, '€', False, True).register())
