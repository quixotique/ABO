# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""A Money object represents an exact amount of a single currency.
"""

import re
import decimal
import pycountry

class RegistryError(Exception):
    pass

class CurrencyMismatch(Exception):
    pass

class Currencies(object):
    pass

class Currency(object):

    _registry = Currencies

    def __new__(cls, code, local_frac_digits=0, local_symbol=None, local_symbol_precedes=False, local_symbol_separated_by_space=False):
        try:
            currency = pycountry.currencies.get(letter=code)
        except KeyError:
            currency = None
        if not currency:
            raise ValueError('invalid ISO 4217 currency code: %r' % (code,))
        code = str(code)
        singleton = getattr(cls._registry, code, None)
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
                traps= (decimal.DivisionByZero, decimal.InvalidOperation, decimal.Inexact))
        self.zero = decimal.Decimal(10, context=self.decimal_context) ** -self.local_frac_digits
        return self

    def register(self, registry=None):
        r'''Register this Currency object in the registry, to make it available globally.
        >>> Currency('USD')
        Currency('USD')
        >>> Currency('USD').register()
        Currencies.USD
        >>> Currency('USD')
        Currencies.USD
        >>> del Currencies.USD
        >>> Currency('USD')
        Currency('USD')
        '''
        if registry is None:
            registry = self._registry
        singleton = getattr(registry, self.code, None)
        if not singleton:
            setattr(registry, self.code, self)
            return self
        assert singleton.code == self.code
        if singleton == self:
            return singleton
        raise RegistryError("%s.%s already set" % (registry.__name__, singleton.code))

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
        singleton = getattr(self._registry, self.code, None)
        if singleton is self:
            return '%s.%s' % (self._registry.__name__, self.code)
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
        try:
            if pycountry.currencies.get(letter=text[:3]).letter == text[:3]:
                return str(text[:3]), text[3:].lstrip()
        except KeyError:
            pass
        try:
            if pycountry.currencies.get(letter=text[-3:]).letter == text[-3:]:
                return str(text[-3:]), text[:-3].rstrip()
        except KeyError:
            pass
        return None, text

    @classmethod
    def extract_currency(cls, text):
        r'''Extract an ISO 4217 currency code prefix or suffix from the given text,
        and return the corresponding Currency object.
        >>> Currency.extract_currency('AUD 27.30')
        (Currencies.AUD, '27.30')
        >>> Currency.extract_currency('1AUD')
        (Currencies.AUD, '1')
        >>> Currency.extract_currency('USD 18.45')
        (None, 'USD 18.45')
        '''
        code, rest = cls.extract_code(text)
        if code:
            try:
                return getattr(cls._registry, code), rest
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
        (Currencies.AUD, Decimal('123'))
        >>> Currency.parse_amount_currency('AUD $-4,567')
        (Currencies.AUD, Decimal('-4567'))
        >>> Currency.parse_amount_currency('AUD -$4,567')
        (Currencies.AUD, Decimal('-4567'))
        >>> Currency.parse_amount_currency('AUD -$-4,567')
        Traceback (most recent call last):
        ValueError: invalid amount: '-$-4,567'
        >>> Currency.parse_amount_currency('AUD $-4,567.8')
        (Currencies.AUD, Decimal('-4567.8'))
        >>> Currency.parse_amount_currency('AUD $+34,567.891')
        (Currencies.AUD, Decimal('34567.891'))
        >>> Currency.parse_amount_currency('123AUD')
        (Currencies.AUD, Decimal('123'))
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
            currency = getattr(cls._registry, code, None)
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
        >>> Currencies.AUD.parse_amount('123')
        Decimal('123.00')
        >>> Currencies.AUD.parse_amount('AUD 123')
        Decimal('123.00')
        >>> Currencies.AUD.parse_amount('123 AUD')
        Decimal('123.00')
        >>> Currencies.AUD.parse_amount('70.45')
        Decimal('70.45')
        >>> Currencies.AUD.parse_amount('-$1,234,567.89')
        Decimal('-1234567.89')
        >>> Currencies.AUD.parse_amount('+.05')
        Decimal('0.05')
        >>> Currencies.AUD.parse_amount('123,456,789.10')
        Decimal('123456789.10')
        >>> Currencies.AUD.parse_amount('AUD $-4,567.8')
        Traceback (most recent call last):
        ValueError: invalid literal for Currencies.AUD: 'AUD $-4,567.8'
        >>> Currencies.AUD.parse_amount('AUD $-4,567.80')
        Decimal('-4567.80')
        >>> Currencies.AUD.parse_amount('70.456')
        Traceback (most recent call last):
        ValueError: invalid literal for Currencies.AUD: '70.456'
        >>> Currencies.AUD.parse_amount('EUR 123')
        Traceback (most recent call last):
        ValueError: currency code of 'EUR 123' should be 'AUD'
        >>> Currencies.AUD.parse_amount('EUR 123')
        Traceback (most recent call last):
        ValueError: currency code of 'EUR 123' should be 'AUD'
        >>> Currencies.AUD.parse_amount('AUD 1.2.3')
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
        >>> Currencies.AUD.quantize(1)
        Decimal('1.00')
        '''
        try:
            return self.decimal_context.quantize(amount, self.zero)
        except decimal.Inexact:
            raise ValueError('invalid literal for %r: %r' % (self, amount))

    def format(self, amount, thousands=False, positive_sign='', positive_prefix='', positive_suffix='', negative_sign='-', negative_prefix='', negative_suffix=''):
        ur'''Return a string representation of the Decimal amount with the
        currency symbol as prefix or suffix.
        >>> Currencies.AUD.format(1)
        u'$1.00'
        >>> Currencies.AUD.format(-1)
        u'$-1.00'
        >>> Currencies.AUD.format(-100, negative_prefix='(', negative_sign='', negative_suffix=')')
        u'($100.00)'
        >>> Currencies.AUD.format(10000000)
        u'$10000000.00'
        >>> Currencies.AUD.format(10000000, thousands=True)
        u'$10,000,000.00'
        >>> Currencies.EUR.format(1) == u'1.00 €'
        True
        '''
        amt = self.quantize(amount)
        fmt = u'{0:,}' if thousands else u'{0}'
        if self.local_symbol:
            fmt = '{4}{1}{2}{3}'+fmt+'{5}' if self.local_symbol_precedes else '{4}{3}'+fmt+'{2}{1}{5}'
        sep = ' ' if self.local_symbol_separated_by_space else ''
        return (fmt.format(amt, self.local_symbol, sep, positive_sign, positive_prefix, positive_suffix) if amt >= 0
                else fmt.format(-amt, self.local_symbol, sep, negative_sign, negative_prefix, negative_suffix))

    def parse_amount_money(self, text):
        r'''Parse given text into a Money object with this currency.
        >>> Currencies.EUR.parse_amount_money('60001')
        Money(60001.00, Currencies.EUR)
        '''
        return Money.from_text(text, currency=self)

    def money(self, amount):
        r'''Convert the given number into a Money object for this currency.
        Raise ValueError if the given amount would have to be rounded (ie, has
        too many decimal places.
        >>> Currencies.AUD.money(1)
        Money(1.00, Currencies.AUD)
        '''
        return Money(amount, self)

class Money(object):

    r'''Represents an exact amount (not fractional) of a given single currency.
    >>> Money(140, Currencies.AUD)
    Money(140.00, Currencies.AUD)
    '''

    def __init__(self, amount, currency):
        self.currency = currency
        self.amount = currency.quantize(amount)

    @classmethod
    def from_text(cls, text, currency=None):
        r'''Parse a text string into a Money object.
        >>> Money.from_text('8071.51 AUD')
        Money(8071.51, Currencies.AUD)
        >>> Money.from_text('-6.99 AUD')
        Money(-6.99, Currencies.AUD)
        '''
        if currency is not None:
            amount = currency.parse_amount(text)
        else:
            currency, number = Currency.extract_currency(text)
            if currency is None:
                raise ValueError('invalid literal for %r.from_text(currency=None): %r' % (type(self).__name__, text,))
            amount = currency.parse_amount(number)
        return cls(amount, currency)

    def __str__(self):
        return '%s %s' % (self.amount, self.currency)

    def __repr__(self):
        return '%s(%s, %r)' % (type(self).__name__, self.amount, self.currency)

    def __nonzero__(self):
        return bool(self.amount)

    def _unmoney(self, other, fmt):
        if isinstance(other, Money):
            if other.currency != self.currency:
                raise CurrencyMismatch(fmt.format(self, other))
            return other.amount
        return other

    def __eq__(self, other):
        return type(self)(self.amount == self._unmoney(other, '{0} == {1}'), self.currency)

    def __ne__(self, other):
        return type(self)(self.amount != self._unmoney(other, '{0} != {1}'), self.currency)

    def __lt__(self, other):
        return type(self)(self.amount < self._unmoney(other, '{0} < {1}'), self.currency)

    def __le__(self, other):
        return type(self)(self.amount <= self._unmoney(other, '{0} <= {1}'), self.currency)

    def __gt__(self, other):
        return type(self)(self.amount > self._unmoney(other, '{0} > {1}'), self.currency)

    def __ge__(self, other):
        return type(self)(self.amount >= self._unmoney(other, '{0} >= {1}'), self.currency)

    def __neg__(self):
        return type(self)(-self.amount, self.currency)

    def __pos__(self):
        return type(self)(+self.amount, self.currency)

    def __abs__(self):
        return type(self)(abs(self.amount), self.currency)

    def __add__(self, other):
        return type(self)(self.amount + self._unmoney(other, '{0} + {1}'), self.currency)

    def __sub__(self, other):
        return type(self)(self.amount - self._unmoney(other, '{0} - {1}'), self.currency)

    def __radd__(self, other):
        return type(self)(self._unmoney(other, '{1} + {0}') + self.amount, self.currency)

    def __rsub__(self, other):
        return type(self)(self._unmoney(other, '{1} - {0}') - self.amount, self.currency)

    def __mul__(self, other):
        return type(self)(self.amount * self._unmoney(other, '{0} * {1}'), self.currency)

    def __rmul__(self, other):
        return type(self)(self._unmoney(other, '{1} * {0}') * self.amount, self.currency)

Currency('AUD', 2, '$', True).register()
Currency('EUR', 2, u'€', False, True).register()

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
