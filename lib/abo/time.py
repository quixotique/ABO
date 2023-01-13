# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Time interval."""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.time
    doctest.testmod(abo.time)

import re
import datetime

re_hours_minutes = re.compile(r'(?:(?:(?P<_abo_time_h1>\d*)(?P<_abo_time_m1>¼|½|¾|⅓|⅔|⅕|⅖|⅗|⅘|:\d\d|\.\d+)h?)|(?:(?:(?P<_abo_time_h2>\d+)\s*[hH])?\s*(?:(?P<_abo_time_m2>\d+)\s*[mM])?)|0)')

def parse_hours_minutes(text):
    """
    >>> import abo.time

    >>> parse_hours_minutes('12h')
    datetime.timedelta(seconds=43200)

    >>> parse_hours_minutes('1:01')
    datetime.timedelta(seconds=3660)

    >>> parse_hours_minutes(u'½h')
    datetime.timedelta(seconds=1800)

    >>> parse_hours_minutes('.1h')
    datetime.timedelta(seconds=360)

    >>> parse_hours_minutes('1m')
    datetime.timedelta(seconds=60)

    """
    return from_hours_minutes_match(re_hours_minutes.fullmatch(text))

def from_hours_minutes_match(match):
    if not match: return None
    hours = int(match.group('_abo_time_h1') or match.group('_abo_time_h2') or '0')
    matched_minutes = match.group('_abo_time_m1') or match.group('_abo_time_m2') or ''
    if matched_minutes.isdigit():
        minutes = int(matched_minutes)
    elif matched_minutes.startswith(':'):
        minutes = int(matched_minutes[1:])
    elif matched_minutes.startswith('.'):
        minutes = int(float(matched_minutes) * 60)
    elif matched_minutes == u'¼':
        minutes = 15
    elif matched_minutes == u'½':
        minutes = 30
    elif matched_minutes == u'¾':
        minutes = 45
    elif matched_minutes == u'⅓':
        minutes = 20
    elif matched_minutes == u'⅔':
        minutes = 40
    elif matched_minutes == u'⅕':
        minutes = 12
    elif matched_minutes == u'⅖':
        minutes = 24
    elif matched_minutes == u'⅗':
        minutes = 36
    elif matched_minutes == u'⅘':
        minutes = 48
    elif not matched_minutes:
        minutes = 0
    else:
        return None
    return datetime.timedelta(hours=hours, minutes=minutes)
