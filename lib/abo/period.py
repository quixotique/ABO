# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Time period language.

>>> import abo.period
>>> abo.period._today = lambda: date(2013, 3, 20)

>>> parse_periods(['from', '1/3/2012', 'to', '16/3/2013'])
[(datetime.date(2012, 3, 1), datetime.date(2013, 3, 16))]

>>> parse_periods(['fy', '2010'])
[(datetime.date(2009, 7, 1), datetime.date(2010, 6, 30))]

>>> parse_periods(['fy'])
[(datetime.date(2012, 7, 1), datetime.date(2013, 6, 30))]

>>> parse_periods(['this', 'fy'])
[(datetime.date(2012, 7, 1), datetime.date(2013, 6, 30))]

>>> parse_periods(['last', 'fy'])
[(datetime.date(2011, 7, 1), datetime.date(2012, 6, 30))]

>>> parse_periods(['next', 'month'])
[(datetime.date(2013, 4, 1), datetime.date(2013, 4, 30))]

>>> parse_periods(['this', 'week'])
[(datetime.date(2013, 3, 18), datetime.date(2013, 3, 24))]

>>> parse_periods(['last', 'week'])
[(datetime.date(2013, 3, 11), datetime.date(2013, 3, 17))]

>>> parse_periods(['q2'])
[(datetime.date(2012, 10, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['q1', '2010'])
[(datetime.date(2009, 7, 1), datetime.date(2009, 9, 30))]

>>> parse_periods(['q4'])
[(datetime.date(2013, 4, 1), datetime.date(2013, 6, 30))]

>>> parse_periods(['last', 'q4'])
[(datetime.date(2012, 4, 1), datetime.date(2012, 6, 30))]

>>> parse_periods(['next', 'q2'])
[(datetime.date(2013, 10, 1), datetime.date(2013, 12, 31))]

>>> parse_periods(['last', 'quarter'])
[(datetime.date(2012, 10, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['this', 'quarter'])
[(datetime.date(2013, 1, 1), datetime.date(2013, 3, 31))]

>>> parse_periods(['next', 'quarter'])
[(datetime.date(2013, 4, 1), datetime.date(2013, 6, 30))]

>>> parse_periods(['last', 'ten', 'years'])
[(datetime.date(2003, 1, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['latest', 'six', 'months'])
[(datetime.date(2012, 9, 1), datetime.date(2013, 2, 28))]

>>> parse_periods(['last', '30', 'days'])
[(datetime.date(2013, 2, 19), datetime.date(2013, 3, 20))]

>>> parse_periods(['last', 'year', 'quarterly']) #doctest: +NORMALIZE_WHITESPACE
[(datetime.date(2012, 1, 1), datetime.date(2012, 3, 31)),
 (datetime.date(2012, 4, 1), datetime.date(2012, 6, 30)),
 (datetime.date(2012, 7, 1), datetime.date(2012, 9, 30)),
 (datetime.date(2012, 10, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['this', 'quarter', 'monthly']) #doctest: +NORMALIZE_WHITESPACE
[(datetime.date(2013, 1, 1), datetime.date(2013, 1, 31)),
 (datetime.date(2013, 2, 1), datetime.date(2013, 2, 28)),
 (datetime.date(2013, 3, 1), datetime.date(2013, 3, 31))]

>>> abo.period._today = lambda: date(2013, 3, 31)

>>> parse_periods(['this', 'month'])
[(datetime.date(2013, 3, 1), datetime.date(2013, 3, 31))]

>>> parse_periods(['last', 'month'])
[(datetime.date(2013, 2, 1), datetime.date(2013, 2, 28))]

>>> parse_periods(['latest', 'two', 'months'])
[(datetime.date(2013, 2, 1), datetime.date(2013, 3, 31))]

>>> parse_periods(['last', '5', 'days'])
[(datetime.date(2013, 3, 27), datetime.date(2013, 3, 31))]

"""

from datetime import (date, datetime, timedelta)

def _today():
    return date.today()

def parse_periods(args):
    periods = _parse_periods(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    return periods

def _parse_periods(args):
    periods = []
    while args:
        if args[0] == 'this':
            which = args[0]
            args.pop(0)
            start, end = parse_this(args)
            periods.append((start, end))
        elif args[0] == 'last':
            which = args[0]
            word = args.pop(0)
            if args < 1:
                raise ValueError("missing argument after 'last'")
            oargs = list(args)
            try:
                start, end = parse_last(args)
            except ValueError:
                args[:] = oargs
                start, end = parse_latest(word, args)
            periods.append((start, end))
        elif args[0] == 'next':
            which = args[0]
            args.pop(0)
            start, end = parse_next(args)
            periods.append((start, end))
        elif args[0] == 'latest':
            word = args.pop(0)
            start, end = parse_latest(word, args)
            periods.append((start, end))
        elif args[0] == 'from':
            args.pop(0)
            if not args:
                raise ValueError("missing argument after 'from'")
            start = parse_fromto(args)[0]
            end = None
            if args and args[0] == 'to':
                args.pop(0)
                if not args:
                    raise ValueError("missing argument after 'to'")
                end = parse_fromto(args)[1]
            periods.append((start, end))
        elif args[0] == 'to':
            args.pop(0)
            if not args:
                raise ValueError("missing argument after 'to'")
            end = parse_fromto(args)[1]
            periods.append((None, end))
        elif args[0] in ('fy', 'q1', 'q2', 'q3', 'q4'):
            unit = args.pop(0)
            year = None
            if args:
                try:
                    year = parse_year(args[0])
                    args.pop(0)
                except ValueError:
                    pass
            if year is not None:
                end = date(year, 6, 30)
                start = date(end.year - 1, 7, 1)
            else:
                start, end = fy_containing(_today())
            if unit[0] == 'q':
                start, end = quarter_of_fy_starting(start, int(unit[1]))
            periods.append((start, end))
        elif args[0] == 'monthly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, months=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        elif args[0] == 'quarterly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, quarters=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        elif args[0] in ('yearly', 'annually'):
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, years=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        else:
            break
    return periods

def parse_whens(args):
    r"""
    >>> import abo.period
    >>> abo.period._today = lambda: date(2013, 3, 20)

    >>> parse_whens(['today'])
    [datetime.date(2013, 3, 20)]
    >>> parse_whens(['yesterday', 'today', 'five', 'days', 'ago', 'tomorrow'])
    [datetime.date(2013, 3, 19), datetime.date(2013, 3, 20), datetime.date(2013, 3, 15), datetime.date(2013, 3, 21)]

    """
    whens = _parse_whens(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    return whens

def parse_when(args):
    r"""
    >>> import abo.period
    >>> abo.period._today = lambda: date(2013, 3, 20)

    >>> parse_when(['today'])
    datetime.date(2013, 3, 20)
    >>> parse_when(['five', 'days', 'ago'])
    datetime.date(2013, 3, 15)
    >>> parse_when(['yesterday'])
    datetime.date(2013, 3, 19)
    >>> parse_when(['start', 'of', 'last', 'year'])
    datetime.date(2012, 1, 1)
    >>> parse_when(['end', 'this', 'fy'])
    datetime.date(2013, 6, 30)

    """
    whens = _parse_whens(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    if len(whens) == 0:
        raise ValueError('missing date')
    if len(whens) > 1:
        raise ValueError('too many dates')
    return whens[0]

def _parse_whens(args):
    whens = []
    while args:
        startend = None
        if args and args[0] in ('start', 'end'):
            startend = args.pop(0)
            if args and args[0] == 'of':
                args.pop(0)
            periods = _parse_periods(args)
            whens += (period[1] if startend == 'end' else period[0] for period in periods)
        else:
            whens.append(parse_date(args))
    return whens

def parse_fromto(args):
    if args[0] == 'this':
        args.pop(0)
        return parse_this(args)
    elif args[0] == 'last':
        args.pop(0)
        return parse_last(args)
    elif args[0] == 'next':
        args.pop(0)
        return parse_next(args)
    elif len(args) >= 3 and args[2] in ('ago', 'hence'):
        amount = parse_amount(args.pop(0))
        unit = args.pop(0)
        if args.pop(0) == 'ago':
            amount = -amount
        return enclosing_range(advance_date_unit(_today(), unit, amount), unit)
    else:
        d = parse_date(args)
    return d, d

def parse_date(args):
    if args[0] in ('now', 'today'):
        d = _today()
        args.pop(0)
    elif args[0] in ('yesterday'):
        d = _today() - timedelta(1)
        args.pop(0)
    elif args[0] in ('tomorrow'):
        d = _today() + timedelta(1)
        args.pop(0)
    elif len(args) >= 3 and args[2] in ('ago', 'hence'):
        amount = parse_amount(args.pop(0))
        unit = args.pop(0)
        if args.pop(0) == 'ago':
            amount = -amount
        d = advance_date_unit(_today(), unit, amount)
    else:
        d = datetime.strptime(args[0], '%d/%m/%Y').date()
        args.pop(0)
    return d

def parse_this(args):
    if not args:
        raise ValueError("missing argument after 'this'")
    unit = args.pop(0)
    return enclosing_range(_today(), unit)

def parse_year(word):
    try:
        year = int(word)
        if year >= 1900 and year <= 9999:
            return year
    except ValueError:
        pass
    raise ValueError('invalid year %r' % (word,))

def parse_amount(word):
    if word.isdigit():
        amount = int(word)
        if amount > 0:
            return amount
        raise ValueError("invalid amount %r" % (word,))
    else:
        try:
            return {'one': 1, 'two': 2, 'three': 3, 'four':4, 'five':5,
                    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                    'eleven': 11, 'twelve': 12}[word]
        except KeyError:
            raise ValueError("unrecognised amount %r" % (word,))

def fy_ending_in(year):
    r'''This function determines the start and end of the financial year.  All
    other FY date calculations derive from this one.  Eventually the EOFY date
    will be configurable.
    '''
    end = date(year, 6, 30)
    start = date(end.year - 1, 7, 1)
    return start, end

def fy_containing(origin):
    start, end = fy_ending_in(origin.year)
    if end < origin:
        start = advance_date(start, years=1, months=0)
        end = advance_date(end, years=1, months=0)
    return start, end

def quarter_of_fy_starting(origin, q):
    assert 1 <= q <= 4
    start = advance_date(origin, quarters= q - 1)
    end = advance_date(start, quarters=1) - timedelta(1)
    return start, end

def enclosing_range(origin, unit):
    if unit in ('day', 'days'):
        start = origin
        end = origin
    elif unit in ('week', 'weeks'):
        start = origin - timedelta(origin.weekday())
        end = start + timedelta(6)
    elif unit in ('month', 'months'):
        start = origin.replace(day=1)
        end = advance_date(start, months=1) - timedelta(1)
    elif unit in ('q', 'quarter', 'quarters'):
        start = origin.replace(day=1, month= origin.month - (origin.month - 1) % 3)
        end = advance_date(start, quarters=1) - timedelta(1)
    elif unit in ('q1', 'q2', 'q3', 'q4'):
        start, end = fy_containing(origin)
        start, end = quarter_of_fy_starting(start, int(unit[1]))
    elif unit in ('year', 'years'):
        start = origin.replace(month=1, day=1)
        end = advance_date(start, years=1) - timedelta(1)
    elif unit in ('fy', 'fys'):
        start, end = fy_containing(origin)
    else:
        raise ValueError("unrecognised unit %r" % unit)
    return start, end

def parse_last(args):
    if not args:
        raise ValueError("missing argument after 'last'")
    today = _today()
    if args[0] in ('fy', 'q1', 'q2', 'q3', 'q4'):
        unit = args.pop(0)
        start, end = fy_containing(today)
        start = advance_date(start, years=-1)
        end = advance_date(end, years=-1)
        if unit[0] == 'q':
            start, end = quarter_of_fy_starting(start, int(unit[1]))
    elif args[0] == 'year':
        args.pop(0)
        start = advance_date(today.replace(day=1, month=1), years=-1)
        end = advance_date(start, years=1) - timedelta(1)
    elif args[0] in ('quarter'):
        unit = args.pop(0)
        start, end = enclosing_range(advance_date_unit(today, unit, -1), unit)
    elif args[0] == 'month':
        args.pop(0)
        start = advance_date(today.replace(day=1), months=-1)
        end = advance_date(start, months=1) - timedelta(1)
    elif args[0] == 'week':
        args.pop(0)
        start = today - timedelta(7 + today.weekday())
        end = start + timedelta(6)
    else:
        start = today.replace(month=parse_monthname(args[0]), day=1)
        args.pop(0)
        if start >= today or start.month == today.month:
            start = start.replace(year=start.year - 1)
        end = advance_date(start, months=1) - timedelta(1)
    return start, end

def parse_next(args):
    if not args:
        raise ValueError("missing month after 'next'")
    today = _today()
    if args[0] in ('fy', 'q1', 'q2', 'q3', 'q4'):
        unit = args.pop(0)
        start, end = fy_containing(today)
        start = advance_date(start, years=1)
        end = advance_date(end, years=1)
        if unit[0] == 'q':
            start, end = quarter_of_fy_starting(start, int(unit[1]))
    elif args[0] == 'year':
        args.pop(0)
        start = advance_date(today.replace(day=1, month=1), years=1)
        end = advance_date(start, years=1) - timedelta(1)
    elif args[0] in ('quarter', 'q1', 'q2', 'q3', 'q4'):
        unit = args.pop(0)
        start, end = enclosing_range(advance_date_unit(today, unit, 1), unit)
    elif args[0] == 'month':
        args.pop(0)
        start = advance_date(today.replace(day=1), months=1)
        end = advance_date(start, months=1) - timedelta(1)
    elif args[0] == 'week':
        args.pop(0)
        start = today + timedelta(7 - today.weekday())
        end = start + timedelta(6)
    else:
        start = today.replace(month=parse_monthname(args[0]), day=1)
        args.pop(0)
        if start <= today or start.month == today.month:
            start = start.replace(year=start.year + 1)
        end = advance_date(start, months=1) - timedelta(1)
    return start, end

def parse_latest(word, args):
    if args < 1:
        raise ValueError("missing amount after %r", word)
    if args < 2:
        raise ValueError("missing unit after %r %r" % (word, args[0],))
    amount = parse_amount(args.pop(0))
    unit = args.pop(0)
    # Range should include today but not tomorrow
    tomorrow = _today() + timedelta(1)
    start = enclosing_range(advance_date_unit(tomorrow, unit, -amount), unit)[0]
    end = enclosing_range(tomorrow, unit)[0] - timedelta(1)
    return start, end

def advance_date_unit(start, unit, amount):
    if unit in ('year', 'years', 'fy', 'fys'):
        return advance_date(start, years=amount)
    elif unit in ('quarter', 'quarters'):
        return advance_date(start, quarters=amount)
    elif unit in ('month', 'months'):
        return advance_date(start, months=amount)
    elif unit in ('day', 'days'):
        return start + timedelta(amount)
    else:
        raise ValueError("unrecognised unit %r" % (unit,))

def parse_monthname(s):
    try:
        return datetime.strptime(s, '%B').month
    except ValueError:
        pass
    return datetime.strptime(s, '%b').month

def advance_date(start, months=0, quarters=0, years=0):
    y = start.year + years
    m = start.month - 1 + months + quarters * 3
    y += m // 12
    m = m % 12
    return start.replace(year=y, month=m + 1)

def _test():
    import doctest
    import abo.period
    return doctest.testmod(abo.period)

if __name__ == "__main__":
    _test()
