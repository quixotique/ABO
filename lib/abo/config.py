# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Configuration settings for an account system.
"""

import os
import os.path
import re
import locale
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
        self.basedir = None
        self.journal_file_paths = []
        self.checkpoint_file_paths = []
        self.chart_file_path = None
        self.heading = None
        self.width = None
        self.maximum_output_width = {}
        text = os.environ.get('ABO_WIDTH')
        if text is not None:
            try:
                self.width = uint(text)
            except ValueError as e:
                warn('ignoring invalid environment variable ABO_WIDTH: %r' % text)

    _regex_encoding = re.compile(r'coding[=:]\s*([-\w.]+)', re.MULTILINE)

    def detect_encoding(self, path, line_count=10):
        r"""Inspect the first few lines of a file, looking for a declared file
        encoding.
        """
        firstlines = []
        with open(path, 'r', encoding='ascii', errors='ignore') as f:
            for line in f:
                firstlines.append(line)
                if len(firstlines) >= line_count:
                    break
        m = self._regex_encoding.search('\n'.join(firstlines))
        return m.group(1) if m else locale.getlocale()[1] or 'ascii'

    def open(self, path, mode='r'):
        return open(path, mode, encoding=self.detect_encoding(path), errors='strict')

    def read_from(self, path):
        with Parser(path) as parser:
            self.basedir = parser.basedir
            self.chart_file_path = os.path.join(parser.basedir, 'accounts')
            parser.add_keyword('journal', self._set_journal)
            parser.add_keyword('heading', self._set_heading)
            parser.add_keyword('checkpoint', self._set_checkpoint)
            parser.add_section_keyword('maximum-output-width', self._set_maximum_output_width)
            parser.parse()
        return self

    def _set_journal(self, parser, word):
        self.journal_file_paths += glob.glob(os.path.join(parser.basedir, word))

    def _set_heading(self, parser, word):
        if self.heading is not None:
            raise ConfigException("heading is already set")
        self.heading = word

    def _set_checkpoint(self, parser, word):
        self.checkpoint_file_paths += glob.glob(os.path.join(parser.basedir, word))

    def _set_maximum_output_width(self, parser, word, section):
        try:
            self.maximum_output_width[section] = uint(word)
        except ValueError as e:
            raise ConfigException("invalid width: " + e)

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
        return date.strftime(r'%-d-%b-%y' if relative_to is None or relative_to.year != date.year else r'%-d-%b')

    @property
    def currency(self):
        global abo
        import abo.money
        return abo.money.Currency.AUD

    def parse_money(self, text):
        return self.currency.parse_amount_money(text)

    def money(self, amount):
        return self.currency.money(amount)

    def format_money(self, amount, symbol=False, thousands=True):
        global abo
        import abo.money
        if not isinstance(amount, abo.money.Money):
            amount = self.money(amount)
        return amount.format(symbol=symbol, thousands=thousands)

    def money_column_width(self):
        return len(self.format_money(self.money(1000000)))

    def balance_column_width(self):
        return self.money_column_width() + 1

    def get_output_widths(self, *args, section=None, fixed=0):
        minimum = fixed
        natural = fixed
        for minw, natw, maxw in args:
            assert minw <= natw, 'minw=%r natw=%r' % (minw, natw)
            assert maxw is None or minw <= maxw, 'minw=%r maxw=%r' % (minw, maxw)
            minimum += minw
            natural += natw
        if self.width: # --width=N option
            if self.width < minimum:
                raise InvalidOption('--width', 'minimum width is %d' % minimum)
            width = self.width
        elif sys.stdout.isatty():
            try:
                width = uint(os.environ['COLUMNS'])
                if width:
                    width = max(width, minimum)
                    maxwidth = self.maximum_output_width.get(section)
                    if maxwidth:
                        width = min(width, maxwidth)
            except (ValueError, KeyError):
                pass
        else:
            width = natural
        surplus = width - minimum
        widths = [width]
        for minw, natw, maxw in args:
            if surplus > 0:
                wid = minw + surplus
                if maxw and wid > maxw:
                    wid = maxw
                surplus -= wid - minw
            else:
                wid = minw
            widths.append(wid)
        return widths

    def cache_dir_path(self):
        return os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pyabo')

class Parser(object):

    def __init__(self, path):
        self.path = path
        self.basedir = os.path.dirname(path)

    def __enter__(self):
        self.instream = open(self.path)
        self.lex = shlex.shlex(self.instream, self.path, posix=True)
        self.lex.whitespace_split = True
        self.error_leader = self.lex.error_leader()
        self.keywords = {}
        self.section_keywords = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self.lex
        return self.instream.__exit__(exc_type, exc_val, exc_tb)

    def add_keyword(self, keyword, handler):
        self.keywords[keyword] = handler

    def add_section_keyword(self, keyword, handler):
        self.section_keywords[keyword] = handler

    def get_token(self):
        err = self.lex.error_leader()
        self.tok = self.lex.get_token()
        if self.tok is not None:
            self.error_leader = err
        return self.tok

    def parse(self):
        try:
            self.get_token()
            while self.tok is not None:
                handler = self.keywords.get(self.tok)
                if handler is not None:
                    self.parse_values(handler)
                    continue
                try:
                    section, tok = self.tok.split('.', 1)
                    handler = self.section_keywords.get(tok)
                    if handler is not None:
                        self.parse_values(handler, section=section)
                        continue
                except TypeError:
                    pass
                break
            if self.tok is not None:
                raise ConfigException("unexpected token: %r" % self.tok)
        except ConfigException as e:
            raise ConfigException(self.error_leader + str(e))

    def parse_values(self, handler, **kwargs):
        self.get_token()
        while self.tok is not None and self.tok != ';':
            handler(self, self.tok, **kwargs)
            self.get_token()
        if self.tok != ';':
            raise ConfigException("expecting ';', got " + ('EOF' if self.tok is None else repr(self.tok)))
        self.get_token()
