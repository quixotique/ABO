# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Time period language."""

if __name__ == "__main__":
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.period
    doctest.testmod(abo.period)

from datetime import (date, datetime, timedelta)

def _today():
    return date.today()

def parse_periods(args):
    """
    >>> import abo.period
    >>> abo.period._today = lambda: date(2013, 3, 20)

    >>> parse_periods(['from', '1/3/2012', 'to', '16/3/2013'])
    [(datetime.date(2012, 3, 1), datetime.date(2013, 3, 16))]

    >>> parse_periods(['to', 'end', 'this', 'year'])
    [(None, datetime.date(2013, 12, 31))]

    >>> parse_periods(['year', '2011'])
    [(datetime.date(2011, 1, 1), datetime.date(2011, 12, 31))]

    >>> parse_periods(['2014'])
    [(datetime.date(2014, 1, 1), datetime.date(2014, 12, 31))]

    >>> parse_periods(['from', 'end', 'last', 'year', 'to', 'start', 'next', 'year'])
    [(datetime.date(2012, 12, 31), datetime.date(2014, 1, 1))]

    >>> parse_periods(['to', 'date'])
    [(None, datetime.date(2013, 3, 20))]

    >>> parse_periods(['fy', '2010'])
    [(datetime.date(2009, 7, 1), datetime.date(2010, 6, 30))]

    >>> parse_periods(['fy'])
    [(datetime.date(2012, 7, 1), datetime.date(2013, 6, 30))]

    >>> parse_periods(['this', 'fy'])
    [(datetime.date(2012, 7, 1), datetime.date(2013, 6, 30))]

    >>> parse_periods(['this', 'fy', 'to', 'date'])
    [(datetime.date(2012, 7, 1), datetime.date(2013, 3, 20))]

    >>> parse_periods(['last', 'fy'])
    [(datetime.date(2011, 7, 1), datetime.date(2012, 6, 30))]

    >>> parse_periods(['fys', '2005-2010'])
    [(datetime.date(2004, 7, 1), datetime.date(2010, 6, 30))]

    >>> parse_periods(['fys', '2005-2010', 'yearly']) #doctest: +NORMALIZE_WHITESPACE
    [(datetime.date(2004, 7, 1), datetime.date(2005, 6, 30)),
     (datetime.date(2005, 7, 1), datetime.date(2006, 6, 30)),
     (datetime.date(2006, 7, 1), datetime.date(2007, 6, 30)),
     (datetime.date(2007, 7, 1), datetime.date(2008, 6, 30)),
     (datetime.date(2008, 7, 1), datetime.date(2009, 6, 30)),
     (datetime.date(2009, 7, 1), datetime.date(2010, 6, 30))]

    >>> parse_periods(['next', 'month'])
    [(datetime.date(2013, 4, 1), datetime.date(2013, 4, 30))]

    >>> parse_periods(['next', 'feb'])
    [(datetime.date(2014, 2, 1), datetime.date(2014, 2, 28))]

    >>> parse_periods(['jan'])
    [(datetime.date(2013, 1, 1), datetime.date(2013, 1, 31))]

    >>> parse_periods(['nov'])
    [(datetime.date(2013, 11, 1), datetime.date(2013, 11, 30))]

    >>> parse_periods(['apr', '2010'])
    [(datetime.date(2010, 4, 1), datetime.date(2010, 4, 30))]

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

    Dividing a period into weeks does not preserve the period's original start and
    end dates.  It produces the sequence of weeks whose start days (Monday) falls
    within the period.

    >>> parse_periods(['this', 'quarter', 'weekly']) #doctest: +NORMALIZE_WHITESPACE
    [(datetime.date(2013, 1, 7), datetime.date(2013, 1, 13)),
    (datetime.date(2013, 1, 14), datetime.date(2013, 1, 20)),
    (datetime.date(2013, 1, 21), datetime.date(2013, 1, 27)),
    (datetime.date(2013, 1, 28), datetime.date(2013, 2, 3)),
    (datetime.date(2013, 2, 4), datetime.date(2013, 2, 10)),
    (datetime.date(2013, 2, 11), datetime.date(2013, 2, 17)),
    (datetime.date(2013, 2, 18), datetime.date(2013, 2, 24)),
    (datetime.date(2013, 2, 25), datetime.date(2013, 3, 3)),
    (datetime.date(2013, 3, 4), datetime.date(2013, 3, 10)),
    (datetime.date(2013, 3, 11), datetime.date(2013, 3, 17)),
    (datetime.date(2013, 3, 18), datetime.date(2013, 3, 24)),
    (datetime.date(2013, 3, 25), datetime.date(2013, 3, 31))]

    Dividing a period into fortnights does not preserve the period's original start
    and end dates.  It produces the sequence of fortnights whose start day (Monday)
    falls within the period.

    >>> parse_periods(['this', 'quarter', 'fortnightly']) #doctest: +NORMALIZE_WHITESPACE
    [(datetime.date(2013, 1, 7), datetime.date(2013, 1, 20)),
    (datetime.date(2013, 1, 21), datetime.date(2013, 2, 3)),
    (datetime.date(2013, 2, 4), datetime.date(2013, 2, 17)),
    (datetime.date(2013, 2, 18), datetime.date(2013, 3, 3)),
    (datetime.date(2013, 3, 4), datetime.date(2013, 3, 17)),
    (datetime.date(2013, 3, 18), datetime.date(2013, 3, 31))]

    >>> abo.period._today = lambda: date(2013, 3, 31)

    >>> parse_periods(['this', 'month'])
    [(datetime.date(2013, 3, 1), datetime.date(2013, 3, 31))]

    >>> parse_periods(['last', 'month'])
    [(datetime.date(2013, 2, 1), datetime.date(2013, 2, 28))]

    >>> parse_periods(['latest', 'two', 'months'])
    [(datetime.date(2013, 2, 1), datetime.date(2013, 3, 31))]

    >>> parse_periods(['last', '5', 'days'])
    [(datetime.date(2013, 3, 27), datetime.date(2013, 3, 31))]

    >>> parse_periods(['3', 'months', 'ago'])
    [(datetime.date(2012, 12, 1), datetime.date(2012, 12, 31))]

    >>> parse_periods(['last', 'year'])
    [(datetime.date(2012, 1, 1), datetime.date(2012, 12, 31))]

    >>> parse_periods(['1/7/2016'])
    [(datetime.date(2016, 7, 1), datetime.date(2016, 7, 1))]

    """
    periods = _parse_periods(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    return periods

def parse_period(args):
    r"""
    >>> import abo.period
    >>> abo.period._today = lambda: date(2017, 4, 26)

    >>> parse_period(['last', '30', 'days'])
    (datetime.date(2017, 3, 28), datetime.date(2017, 4, 26))
    """
    periods = _parse_periods(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    if len(periods) == 0:
        raise ValueError('missing period')
    if len(periods) > 1:
        raise ValueError('too many periods')
    return periods[0]

def parse_whens(args):
    r"""
    >>> import abo.period
    >>> abo.period._today = lambda: date(2013, 3, 20)

    >>> parse_whens(['today'])
    [datetime.date(2013, 3, 20)]
    >>> parse_whens(['yesterday', 'today', 'five', 'days', 'ago', 'tomorrow'])
    [datetime.date(2013, 3, 19), datetime.date(2013, 3, 20), datetime.date(2013, 3, 15), datetime.date(2013, 3, 21)]
    >>> parse_whens(['start', 'last', 'ten', 'years'])
    [datetime.date(2003, 1, 1)]
    >>> parse_whens(['end', 'last', 'ten', 'years'])
    [datetime.date(2012, 12, 31)]
    >>> parse_whens(['start', 'last', 'ten', 'years', 'yearly']) #doctest: +NORMALIZE_WHITESPACE
    [datetime.date(2003, 1, 1),
     datetime.date(2004, 1, 1),
     datetime.date(2005, 1, 1),
     datetime.date(2006, 1, 1),
     datetime.date(2007, 1, 1),
     datetime.date(2008, 1, 1),
     datetime.date(2009, 1, 1),
     datetime.date(2010, 1, 1),
     datetime.date(2011, 1, 1),
     datetime.date(2012, 1, 1)]
    >>> parse_whens(['end', 'last', 'ten', 'years', 'yearly']) #doctest: +NORMALIZE_WHITESPACE
    [datetime.date(2003, 12, 31),
     datetime.date(2004, 12, 31),
     datetime.date(2005, 12, 31),
     datetime.date(2006, 12, 31),
     datetime.date(2007, 12, 31),
     datetime.date(2008, 12, 31),
     datetime.date(2009, 12, 31),
     datetime.date(2010, 12, 31),
     datetime.date(2011, 12, 31),
     datetime.date(2012, 12, 31)]
    >>> parse_whens(['end', 'last', 'three', 'fys', 'yearly']) #doctest: +NORMALIZE_WHITESPACE
    [datetime.date(2010, 6, 30), datetime.date(2011, 6, 30), datetime.date(2012, 6, 30)]
    >>> parse_whens(['2nd', 'friday', 'in', 'this', 'fy', 'fortnightly']) #doctest: +NORMALIZE_WHITESPACE
    [datetime.date(2012, 7, 13),
     datetime.date(2012, 7, 27),
     datetime.date(2012, 8, 10),
     datetime.date(2012, 8, 24),
     datetime.date(2012, 9, 7),
     datetime.date(2012, 9, 21),
     datetime.date(2012, 10, 5),
     datetime.date(2012, 10, 19),
     datetime.date(2012, 11, 2),
     datetime.date(2012, 11, 16),
     datetime.date(2012, 11, 30),
     datetime.date(2012, 12, 14),
     datetime.date(2012, 12, 28),
     datetime.date(2013, 1, 11),
     datetime.date(2013, 1, 25),
     datetime.date(2013, 2, 8),
     datetime.date(2013, 2, 22),
     datetime.date(2013, 3, 8),
     datetime.date(2013, 3, 22),
     datetime.date(2013, 4, 5),
     datetime.date(2013, 4, 19),
     datetime.date(2013, 5, 3),
     datetime.date(2013, 5, 17),
     datetime.date(2013, 5, 31),
     datetime.date(2013, 6, 14),
     datetime.date(2013, 6, 28)]
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
    >>> parse_when(['end', 'this', 'year'])
    datetime.date(2013, 12, 31)
    >>> parse_when(['eofy'])
    datetime.date(2013, 6, 30)
    >>> parse_when(['eofy', '2010'])
    datetime.date(2010, 6, 30)
    >>> parse_when(['eoq3'])
    datetime.date(2013, 3, 31)
    >>> parse_when(['start', 'of', 'this', 'month'])
    datetime.date(2013, 3, 1)
    >>> parse_when(['first', 'wednesday', 'this', 'month'])
    datetime.date(2013, 3, 6)
    >>> parse_when(['4th', 'wednesday', 'this', 'month'])
    datetime.date(2013, 3, 27)
    >>> parse_when(['fifth', 'wednesday', 'this', 'month'])
    Traceback (most recent call last):
    ValueError: no fifth wednesday in period from 1/3/2013 to 31/3/2013
    >>> parse_when(['50th', 'sunday', 'in', 'this', 'year'])
    datetime.date(2013, 12, 15)
    >>> parse_when(['last', 'sunday', 'this', 'year'])
    datetime.date(2013, 12, 29)
    """
    whens = _parse_whens(args)
    if args:
        raise ValueError("unrecognised argument '%s'" % args[0])
    if len(whens) == 0:
        raise ValueError('missing date')
    if len(whens) > 1:
        raise ValueError('too many dates')
    return whens[0]

def _parse_periods(args):
    periods = []
    while args:
        if periods and args[0] == 'weekly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                start += timedelta((7 - start.weekday()) % 7)
                while start <= end:
                    newperiods.append((start, start + timedelta(6)))
                    start += timedelta(7)
            periods = newperiods
        elif periods and args[0] == 'fortnightly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                start += timedelta((7 - start.weekday()) % 7)
                while start <= end:
                    newperiods.append((start, start + timedelta(13)))
                    start += timedelta(14)
            periods = newperiods
        elif periods and args[0] == 'monthly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, months=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        elif periods and args[0] == 'quarterly':
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, quarters=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        elif periods and args[0] in ('yearly', 'annually'):
            args.pop(0)
            newperiods = []
            for start, end in periods:
                while start < end:
                    next_start = advance_date(start, years=1)
                    newperiods.append((start, min(next_start - timedelta(1), end)))
                    start = next_start
            periods = newperiods
        else:
            try:
                periods.append(_parse_period(args))
            except ValueError:
                break
    return periods

def _parse_period(args):
    if args[0] == 'this':
        which = args[0]
        args.pop(0)
        start, end = parse_this(args)
        if len(args) >= 2 and args[:2] == ['to', 'date']:
            end = _today()
            args.pop(0)
            args.pop(0)
        return start, end
    elif args[0] == 'last':
        which = args[0]
        word = args.pop(0)
        if len(args) < 1:
            raise ValueError("missing argument after 'last'")
        oargs = list(args)
        try:
            return parse_last(args)
        except ValueError:
            args[:] = oargs
            return parse_latest(word, args)
    elif args[0] == 'next':
        which = args[0]
        args.pop(0)
        return parse_next(args)
    elif args[0] == 'latest':
        word = args.pop(0)
        return parse_latest(word, args)
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
        return start, end
    elif args[0] == 'to':
        args.pop(0)
        if not args:
            raise ValueError("missing argument after 'to'")
        if args[0] == 'date':
            end = _today()
            args.pop(0)
        else:
            end = parse_fromto(args)[1]
        return None, end
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
        return start, end
    elif args[0] == 'fys':
        args.pop(0)
        if not args:
            raise ValueError("missing argument after 'fys'")
        first, last = parse_range(args[0], parse_year)
        if first >= last:
            raise ValueError("invalid range %r", args[0])
        args.pop(0)
        return fy_ending_in(first)[0], fy_ending_in(last)[1]
    elif args[0] in ('y', 'year'):
        unit = args.pop(0)
        if not args:
            raise ValueError("missing argument after %r" % unit)
        year = parse_year(args[0])
        args.pop(0)
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        return start, end
    else:
        try:
            year = parse_year(args[0])
            args.pop(0)
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            return start, end
        except ValueError:
            pass
        try:
            month = parse_monthname(args[0])
            args.pop(0)
            year = _today().year
            if args:
                try:
                    year = parse_year(args[0])
                    args.pop(0)
                except ValueError:
                    pass
            start = date(year, month, 1)
            end = advance_date(start, months=1) - timedelta(1)
            return start, end
        except ValueError:
            pass
        return parse_fromto(args)

def _parse_whens(args):
    whens = []
    while args:
        startend = None
        if args[0] in ('start', 'end'):
            startend = args.pop(0)
            if args and args[0] == 'of':
                args.pop(0)
            periods = _parse_periods(args)
            whens += (period[1] if startend == 'end' else period[0] for period in periods)
        else:
            try:
                ordinal = ''
                which = 1
                if args[0] != 'last':
                    which = parse_ordinal(args[0])
                    ordinal = args.pop(0)
            except (IndexError, ValueError):
                whens.append(parse_date(args))
            else:
                last = ''
                if args and args[0] == 'last':
                    last = args.pop(0)
                if not args:
                    raise ValueError('missing day name after ' + ' '.join(repr(w) for w in [ordinal, last] if w))
                weekday = parse_weekday_name(args[0])
                weekday_name = args.pop(0)
                of = ''
                if args and args[0] in ('in', 'of'):
                    of = args.pop(0)
                if not args:
                    raise ValueError('missing period after ' + ' '.join(repr(w) for w in [ordinal, last, weekday_name, of] if w))
                periods = _parse_periods(args)
                for start, end in periods:
                    if last:
                        day = end - timedelta((start.weekday() - weekday + 7) % 7) - timedelta(7) * (which - 1)
                        if day < start:
                            raise ValueError('no %s in period from %s to %s' % (
                                ' '.join(w for w in [ordinal, last, weekday_name] if w),
                                start.strftime('%-d/%-m/%Y'),
                                end.strftime('%-d/%-m/%Y')))
                    else:
                        day = start + timedelta((weekday + 7 - start.weekday()) % 7) + timedelta(7) * (which - 1)
                        if day > end:
                            raise ValueError('no %s in period from %s to %s' % (
                                ' '.join(w for w in [ordinal, weekday_name] if w),
                                start.strftime('%-d/%-m/%Y'),
                                end.strftime('%-d/%-m/%Y')))
                    whens.append(day)
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
    elif args[0] in ('start', 'end'):
        startend = args.pop(0)
        if args and args[0] == 'of':
            args.pop(0)
        start, end = _parse_period(args)
        d = end if startend == 'end' else start
    elif args[0] in ('eofy', 'eoq1', 'eoq2', 'eoq3', 'eoq4'):
        unit = args.pop(0)[2:]
        year = None
        if args:
            try:
                year = parse_year(args[0])
                args.pop(0)
            except ValueError:
                pass
        if year is not None:
            end = date(year, 6, 30)
        else:
            start, end = fy_containing(_today())
        if unit[0] == 'q':
            start, end = quarter_of_fy_starting(start, int(unit[1]))
        d = end
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
    if len(args) < 1:
        raise ValueError("missing amount after %r", word)
    if len(args) < 2:
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

def parse_weekday_name(word):
    r'''
    >>> parse_weekday_name('monday')
    0
    >>> parse_weekday_name('friday')
    4
    >>> parse_weekday_name('Sun')
    6
    >>> parse_weekday_name('tues')
    1
    >>> parse_weekday_name('tuesd')
    Traceback (most recent call last):
    ValueError: unrecognised day 'tuesd'
    '''
    try:
        return {'mon': 0, 'monday': 0,
                'tue': 1, 'tues': 1, 'tuesday': 1,
                'wed': 2, 'wednesday': 2,
                'thu': 3, 'thurs': 3, 'thursday': 3,
                'fri': 4, 'friday': 4,
                'sat': 5, 'saturday': 5,
                'sun': 6, 'sunday': 6}[word.lower()]
    except KeyError:
        pass
    raise ValueError("unrecognised day %r" % (word,))

def parse_monthname(s):
    try:
        return datetime.strptime(s, '%B').month
    except ValueError:
        pass
    return datetime.strptime(s, '%b').month

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

def parse_range(word, parser):
    try:
        first, second = word.split('-', 1)
    except ValueError:
        raise ValueError("not a range %r" % (word,))
    return parser(first), parser(second)

def parse_ordinal(word):
    r'''
    >>> parse_ordinal('1st')
    1
    >>> parse_ordinal('101st')
    101
    >>> parse_ordinal('eleventh')
    11
    >>> parse_ordinal('0th')
    Traceback (most recent call last):
    ValueError: unrecognised ordinal '0th'
    >>> parse_ordinal('50th')
    50
    '''
    if (    ((   word.endswith('1st') or word.endswith('2nd') or word.endswith('3rd')
              or word.endswith('4th') or word.endswith('5th') or word.endswith('6th')
              or word.endswith('7th') or word.endswith('8th') or word.endswith('9th')
              or word.endswith('0th')) and word[:-2].isdigit())
         or word in ('11th', '12th', '13th')):
        amount = int(word[:-2])
        if amount:
            return amount
    else:
        try:
            return {'first': 1, 'second': 2, 'third': 3, 'fourth':4, 'fifth':5,
                    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
                    'eleventh': 11, 'twelfth': 12}[word]
        except KeyError:
            pass
    raise ValueError("unrecognised ordinal %r" % (word,))

def advance_date(start, months=0, quarters=0, years=0):
    y = start.year + years
    m = start.month - 1 + months + quarters * 3
    y += m // 12
    m = m % 12
    return start.replace(year=y, month=m + 1)
