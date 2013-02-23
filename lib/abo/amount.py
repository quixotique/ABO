"""A Money object represents an exact amount of a single currency.
"""

import re
import decimal
import pycountry

class Currency(object):

    amount_regex = re.compile(r'\d+(\.\d+)?|\.\d+')

    _singletons = {}

    def __new__(cls, code, local_frac_digits=0, local_symbol=None, local_symbol_precedes=False, local_symbol_separated_by_space=False, ):
        try:
            currency = pycountry.currencies.get(letter=code)
        except KeyError:
            currency = None
        if not currency:
            raise ValueError('invalid ISO 4217 currency code: %r' % (code,))
        code = str(code)
        singleton = cls._singletons.get(code)
        if singleton:
            assert singleton.code == code
            assert singleton.local_frac_digits == local_frac_digits
            assert singleton.local_symbol == local_symbol
            assert singleton.local_symbol_precedes == local_symbol_precedes
            assert singleton.local_symbol_separated_by_space == local_symbol_separated_by_space
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
        self._singletons[code] = self
        return self

    def __str__(self):
        return self.code

    def __repr__(self):
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
        and return the corresponsing Currency object.
        >>> Currency('AUD', 2, '$', True)
        Currency('AUD')
        >>> Currency.extract_currency('AUD 27.30')
        (Currency('AUD'), '27.30')
        >>> Currency.extract_currency('1AUD')
        (Currency('AUD'), '1')
        >>> Currency.extract_currency('USD 18.45')
        (None, 'USD 18.45')
        '''
        try:
            return cls._singletons[text[:3]], text[3:].lstrip()
        except KeyError:
            pass
        try:
            return cls._singletons[text[-3:]], text[:-3].rstrip()
        except KeyError:
            pass
        return None, text

    def parse_amount(self, text):
        r'''Parse given text as a decimal amount of this currency.
        >>> Currency('AUD', 2).parse_amount('123')
        Decimal('123')
        >>> Currency('AUD', 2).parse_amount('AUD 123')
        Decimal('123')
        >>> Currency('AUD', 2).parse_amount('USD 123')
        Traceback (most recent call last):
        ValueError: invalid amount: 'USD 123'
        >>> Currency('USD')
        Currency('USD')
        >>> Currency('AUD', 2).parse_amount('USD 123')
        Traceback (most recent call last):
        ValueError: currency code of 'USD 123' should be 'AUD' 
        '''
        currency, amount = self.extract_currency(text)
        if currency is not None and currency is not self:
            raise ValueError('currency code of %r should be %r' % (text, self.code))
        m = self.amount_regex.search(amount)
        if not m:
            raise ValueError('invalid amount: %r' % (amount,))
        pre = amount[:m.start(0)]
        numeric = m.group(0)
        post = amount[m.end(0):]
        if self.local_symbol:
            if self.local_symbol_precedes:
                if pre.startswith(self.local_symbol):
                    pre = pre[len(self.local_symbol):].lstrip()
            else:
                if post.endswith(self.local_symbol):
                    post = post[:-len(self.local_symbol)].rstrip()
        if pre or post:
            raise ValueError('invalid amount: %r' % (amount,))
        return decimal.Decimal(numeric, context=self.decimal_context)

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

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
