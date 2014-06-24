# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Configuration settings for an account system.
"""

import os
import os.path
import sys

class ConfigException(Exception):
    pass

class Config(object):

    def __init__(self):
        self.input_file_paths = []
        self.chart_file_path = None
        self.width = None

    def read_from(self, path):
        basedir = os.path.dirname(path)
        self.input_file_paths = [os.path.join(basedir, line.rstrip('\n')) for line in open(path, 'rU')]
        self.chart_file_path = os.path.join(basedir, 'accounts')
        return self

    def apply_options(self, opts):
        self.width = 0 if opts['--wide'] else int(opts['--width']) if opts['--width'] else None
        return self

    def load(self):
        trydir = os.path.abspath('.')
        while trydir != '/':
            trypath = os.path.join(trydir, '.pyabo')
            if os.path.isfile(trypath):
                return self.read_from(trypath)
            trydir = os.path.dirname(trydir)
        raise ConfigException('no configuration file')

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
        return self.width if self.width is not None else int(os.environ.get('COLUMNS', 80))

    def cache_dir_path(self):
        return os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pyabo')
