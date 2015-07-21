# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Configuration settings for an account system.
"""

import os
import os.path
import glob
import shlex
from itertools import chain
import sys

class InvalidInput(ValueError):

    def __init__(self, label, cause=None):
        ValueError.__init__(self)
        self.label = label
        self.cause = cause
        self.args = (label, cause)

    def __str__(self):
        if self.cause is not None:
            return '%s: %s' % (self.label, self.cause)
        return self.label

class InvalidArg(InvalidInput):
    pass

class InvalidOption(InvalidInput):
    pass

class InvalidEnviron(InvalidInput):
    pass

class ConfigException(Exception):
    pass

def warn(text):
    print('Warning: %s' % (text,), file=sys.stderr)

def uint(text):
    i = int(text)
    if i < 0:
        raise ValueError('invalid unsigned int: %d' % i)
    return i

class Config(object):

    def __init__(self):
        self.journal_file_paths = []
        self.chart_file_path = None
        self.width = None
        text = os.environ.get('PYABO_WIDTH')
        if text is not None:
            try:
                self.width = uint(text)
            except ValueError as e:
                warn('ignoring invalid environment variable PYABO_WIDTH: %r' % text)

    def read_from(self, path):
        basedir = os.path.dirname(path)
        with open(path) as f:
            lex = shlex.shlex(f, path, posix=True)
            lex.whitespace_split = True
            import sys
            err = lex.error_leader()
            #print(err, file=sys.stderr)
            tok = lex.get_token()
            while tok is not None:
                if tok == 'journal':
                    err = lex.error_leader()
                    #print(err, file=sys.stderr)
                    tok = lex.get_token()
                    while tok is not None and tok != ';':
                        self.journal_file_paths += glob.glob(os.path.join(basedir, tok))
                        err = lex.error_leader()
                        tok = lex.get_token()
                    if tok != ';':
                        raise ConfigException(err + "expecting ';', got " + ('EOF' if tok is None else repr(tok)))
                    err = lex.error_leader()
                    tok = lex.get_token()
                else:
                    break
            if tok is not None:
                raise ConfigException(err + "unknown token: %r" % tok)
        self.chart_file_path = os.path.join(basedir, 'accounts')
        return self

    def apply_options(self, opts):
        if opts['--wide']:
            self.width = 0
        elif opts['--width']:
            try:
                self.width = uint(opts['--width'])
            except ValueError as e:
                raise InvalidOption('--width', e)
        return self

    def load(self):
        trydir = os.path.abspath('.')
        while trydir != '/':
            trypath = os.path.join(trydir, '.pyabo')
            if os.path.isfile(trypath):
                return self.read_from(trypath)
            trydir = os.path.dirname(trydir)
        raise ConfigException('no configuration file')

    def format_date_short(self, date, relative_to=None):
        return date.strftime(r'%-d-%b-%y' if relative_to is not None and relative_to.year != date.year else r'%-d-%b')

    @property
    def currency(self):
        global abo
        import abo.money
        return abo.money.Currency.AUD

    def parse_money(self, text):
        return self.currency.parse_amount_money(text)

    def money(self, amount):
        return self.currency.money(amount)

    def format_money(self, amount):
        global abo
        import abo.money
        if not isinstance(amount, abo.money.Money):
            amount = self.money(amount)
        return amount.format(symbol=False, thousands=True)

    def money_column_width(self):
        return len(self.format_money(self.money(1000000)))

    def balance_column_width(self):
        return self.money_column_width() + 1

    def output_width(self):
        if self.width is not None:
            return self.width
        try:
            return uint(os.environ['COLUMNS'])
        except (ValueError, KeyError):
            return 80

    def cache_dir_path(self):
        return os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pyabo')
