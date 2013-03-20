# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Time period language.

>>> def _today(): return date(2013, 3, 20)

>>> parse_periods(['from', '1/3/2012', 'to', '16/3/2013'])
[(datetime.date(2012, 3, 1), datetime.date(2013, 3, 16))]

>>> parse_periods(['fy', '2010'])
[(datetime.date(2009, 7, 1), datetime.date(2010, 6, 30))]

>>> parse_periods(['last', 'fy'])
[(datetime.date(2011, 7, 1), datetime.date(2012, 6, 30))]

>>> parse_periods(['next', 'month'])
[(datetime.date(2013, 4, 1), datetime.date(2013, 4, 30))]

>>> parse_periods(['last', 'quarter'])
[(datetime.date(2012, 10, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['next', 'quarter'])
[(datetime.date(2013, 4, 1), datetime.date(2013, 6, 30))]

>>> parse_periods(['last', 'ten', 'years'])
[(datetime.date(2003, 1, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['latest', 'six', 'months'])
[(datetime.date(2012, 9, 1), datetime.date(2013, 2, 28))]

>>> parse_periods(['last', 'year', 'quarterly']) #doctest: +NORMALIZE_WHITESPACE
[(datetime.date(2012, 1, 1), datetime.date(2012, 3, 31)),
 (datetime.date(2012, 4, 1), datetime.date(2012, 6, 30)),
 (datetime.date(2012, 7, 1), datetime.date(2012, 9, 30)),
 (datetime.date(2012, 10, 1), datetime.date(2012, 12, 31))]

>>> parse_periods(['this', 'quarter', 'monthly']) #doctest: +NORMALIZE_WHITESPACE
[(datetime.date(2013, 1, 1), datetime.date(2013, 1, 31)),
 (datetime.date(2013, 2, 1), datetime.date(2013, 2, 28)),
 (datetime.date(2013, 3, 1), datetime.date(2013, 3, 31))]

"""

from datetime import (date, datetime, timedelta)

def _today():
    return date.today()

def parse_periods(args):
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
                args = oargs
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
        elif args[0] == 'fy':
            args.pop(0)
            if not args:
                raise ValueError("missing year after 'fy'")
            end = date(int(args.pop(0)), 6, 30)
            start = date(end.year - 1, 7, 1)
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
                    next_start = advance_date(start, months=3)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        else:
            raise ValueError("unrecognised argument '%s'" % args[0])
    return periods

def parse_fromto(args):
    if args[0] in ('now', 'today'):
        args.pop(0)
        d = _today()
    elif args[0] == 'this':
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
        d = datetime.strptime(args[0], '%d/%m/%Y').date()
        args.pop(0)
    return d, d

def parse_this(args):
    if not args:
        raise ValueError("missing argument after 'this'")
    unit = args.pop(0)
    return enclosing_range(_today(), unit)

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

def enclosing_range(origin, unit):
    if unit in ('day', 'days'):
        start = origin
        end = origin
    elif unit in ('month', 'months'):
        start = origin.replace(day=1)
        end = advance_date(start, months=1) - timedelta(1)
    elif unit in ('quarter', 'quarters'):
        start = origin.replace(day=1, month= origin.month - (origin.month - 1) % 3)
        end = advance_date(start, months=3) - timedelta(1)
    elif unit in ('year', 'years'):
        start = origin.replace(month=1, day=1)
        end = advance_date(start, years=1) - timedelta(1)
    elif unit == 'fy':
        end = origin.replace(month=6, day=30)
        if origin > end:
            end = advance_date(end, years=1, months=0)
        start = date(end.year - 1, 7, 1)
    else:
        raise ValueError("unrecognised unit %r" % unit)
    return start, end

def parse_last(args):
    if not args:
        raise ValueError("missing argument after 'last'")
    today = _today()
    if args[0] == 'fy':
        args.pop(0)
        end = today.replace(day=30, month=6)
        if end >= today:
            end = advance_date(end, years=-1)
        start = advance_date(end, years=-1) + timedelta(1)
    elif args[0] == 'year':
        args.pop(0)
        start = advance_date(today.replace(day=1, month=1), years=-1)
        end = advance_date(start, years=1) - timedelta(1)
    elif args[0] == 'quarter':
        unit = args.pop(0)
        start, end = enclosing_range(advance_date_unit(today, unit, -1), unit)
    elif args[0] == 'month':
        args.pop(0)
        start = advance_date(today.replace(day=1), months=-1)
        end = advance_date(start, months=1) - timedelta(1)
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
    if args[0] == 'fy':
        args.pop(0)
        start = today.replace(day=1, month=7)
        if start <= today:
            start = advance_date(start, years=1)
        end = advance_date(start, years=1) - timedelta(1)
    elif args[0] == 'year':
        args.pop(0)
        start = advance_date(today.replace(day=1, month=1), years=1)
        end = advance_date(start, years=1) - timedelta(1)
    elif args[0] == 'quarter':
        unit = args.pop(0)
        start, end = enclosing_range(advance_date_unit(today, unit, 1), unit)
    elif args[0] == 'month':
        args.pop(0)
        start = advance_date(today.replace(day=1), months=1)
        end = advance_date(start, months=1) - timedelta(1)
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
    start = enclosing_range(advance_date_unit(_today(), unit, -amount), unit)[0]
    end = enclosing_range(_today(), unit)[0] - timedelta(1)
    return start, end

def advance_date_unit(start, unit, amount):
    if unit in ('year', 'years'):
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
    return doctest.testmod()

if __name__ == "__main__":
    _test()
