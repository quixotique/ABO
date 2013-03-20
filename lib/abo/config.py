# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Configuration settings for an account system.
"""

import os
import os.path
import sys
import abo.money

currency = abo.money.Currencies.AUD

def parse_money(text):
    return currency.parse_amount_money(text)

def money(amount):
    return currency.money(amount)

def format_money(money):
    return money.format(symbol=False, thousands=True)

def money_column_width():
    return len(format_money(money(1000000)))

def balance_column_width():
    return money_column_width() + 1

class Config(object):

    def __init__(self, path):
        cwd = os.getcwd()
        self.input_file_paths = [os.path.join(cwd, line.rstrip('\n')) for line in open(path, 'rU')]

def config():
    return Config('.pyabo')

def output_width():
    return int(os.environ.get('COLUMNS', 80))
