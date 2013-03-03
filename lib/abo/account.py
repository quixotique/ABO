# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Account object.
"""

import re

_regex_account_name = re.compile(r'^[A-Za-z0-9_]+$')

def parse_account_name(text):
    m = _regex_account_name.match(text) 
    if m:
        return m.group(0)
    raise ValueError('invalid account name: %r' % (text,))
