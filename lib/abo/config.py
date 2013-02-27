# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Configuration settings for an account system.
"""

import abo.money

currency = abo.money.Currencies.AUD

def parse_money(text):
    return currency.parse_amount_money(text)

def money(amount):
    return currency.money(amount)
