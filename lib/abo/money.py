# vim: sw=4 sts=4 et fileencoding=utf8 nomod

"""A Money object represents an exact amount of a single currency.
"""

import re
import decimal
import pycountry

class RegistryError(Exception):
    pass

class Currencies(object):
    pass

class Currency(object):

    _registry = Currencies
    _amount_regex = re.compile(r'\d+(\.\d+)?|\.\d+')

    def __new__(cls, code, local_frac_digits=0, local_symbol=None, local_symbol_precedes=False, local_symbol_separated_by_space=False, ):
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
                prec=self.local_frac_digits,
                rounding=decimal.ROUND_HALF_UP,
                traps=(decimal.DivisionByZero, decimal.InvalidOperation, decimal.Inexact))
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
        if (    singleton.local_frac_digits == self.local_frac_digits
            and singleton.local_symbol == self.local_symbol
            and singleton.local_symbol_precedes == self.local_symbol_precedes
            and singleton.local_symbol_separated_by_space == self.local_symbol_separated_by_space):
            return singleton
        else:
            raise RegistryError("%s.%s already set" % (registry.__name__, singleton.code))

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

    @classmethod
    def parse_amount_code(cls, text, default_currency=None):
        r'''Parse given text as a Decimal and a currency code.
        >>> Currency.parse_amount_code('123')
        Traceback (most recent call last):
        ValueError: missing currency code in '123'
        >>> Currency.parse_amount_code('AUD 123')
        (Currencies.AUD, Decimal('123'))
        >>> Currency.parse_amount_code('123AUD')
        (Currencies.AUD, Decimal('123'))
        >>> Currency.parse_amount_code('AUD 1.2.3')
        Traceback (most recent call last):
        ValueError: invalid amount: '1.2.3'
        >>> Currency.parse_amount_code('123 USD')
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
        numeric = m.group(0)
        post = amount[m.end(0):]
        if currency.local_symbol:
            if currency.local_symbol_precedes:
                if pre.startswith(currency.local_symbol):
                    pre = pre[len(currency.local_symbol):].lstrip()
            else:
                if post.endswith(currency.local_symbol):
                    post = post[:-len(currency.local_symbol)].rstrip()
        if pre or post:
            raise ValueError('invalid amount: %r' % (amount,))
        return currency, decimal.Decimal(numeric, context=currency.decimal_context)

    def parse_amount(self, text):
        r'''Parse given text as a decimal amount of this currency.
        >>> Currencies.AUD.parse_amount('123')
        Decimal('123')
        >>> Currencies.AUD.parse_amount('AUD 123')
        Decimal('123')
        >>> Currencies.AUD.parse_amount('123 AUD')
        Decimal('123')
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
        currency, amount = self.parse_amount_code(text, default_currency=self)
        if currency is not self:
            raise ValueError('currency code of %r should be %r' % (text, self.code))
        return amount

    def format(self, amount):
        pass

class Money(object):

    def __new__(cls, text, currency=None):
        if currency is None:
            currency, amount = Currency.extract_currency(amount)
            if currency is None:
                raise ValueError('invalid literal for Money(currency=None): %r' % (text,))
        self = super(Money, cls).__new__(cls)
        self.amount = currency.parse_amount(amount)
        return self

Currency('AUD', 2, '$', True).register()
Currency('EUR', 2, '€', False).register()

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
