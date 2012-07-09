package ABO::Date::_gregorian;

use ABO::Date;
@ISA = qw(
	ABO::Date
);

use strict;
use Carp;

# This module uses the 1st of January, 1AD as the epoch, which is a
# Saturday.  (Year zero does not exist; year numbering goes 2 BC, 1 BC,
# 1 AD, 2 AD, etc.)  This module cannot represent dates falling before
# this epoch.  This module suffers from the Y10K bug -- it cannot
# represent dates beyond the 31st of December, 9999.
#
# The date 1st January, 1AD corresponds to day = 1, just to be perverse.

my $epoch_day = 0;
my $epoch_weekday = 6; # Saturday
my $year_min = 1;
my $year_max = 9999;
my $month_min = 1;
my $month_max = 12;
my $day_min = 1;
my $days_in_week = 7;
my $months_in_year = $month_max - $month_min + 1;
my $days_in_non_leap_year = 365;
my $days_in_non_leap_century = $days_in_non_leap_year * 100 + 24;

# Methods.

sub _convert
{
	my ($self, $date) = @_;
	my $day;
	if (UNIVERSAL::isa($date, __PACKAGE__)) {
		$day = $$date;
	}
	elsif (ref $date eq 'ARRAY') {
		if (@$date == 3) {
			$day = _reform(_dmy_to_day(@$date));
		}
		elsif (@$date == 2) {
			$day = _reform(_dm_to_day(@$date));
		}
		elsif (@$date == 9) {
			$day = _reform(_tm_to_day(@$date));
		}
		else {
			Carp::croak "bad array arguments @$date";
		}
	}
	elsif (!ref $date) {
		$day = $self->_parse_date(\$date);
	}
	else {
		Carp::croak "bad arguments $date";
	}
	return undef unless defined $day;
	return $day;
}

sub format
{
	my $self = shift;
	return $self->_format_date_str(@_);
}

sub day_month_year
{
	my $self = shift;
	return _day_to_dmy(_unreform($$self));
}

sub day
{
	my $self = shift;
	return ($self->day_month_year)[0];
}

sub month
{
	my $self = shift;
	return ($self->day_month_year)[1];
}

sub year
{
	my $self = shift;
	return ($self->day_month_year)[2];
}

sub weekday
{
	my $self = shift;
	return _day_to_weekday($$self);
}

sub yearday
{
	my $self = shift;
	my $ud = _unreform($$self);
	my ($year, $yday) = _day_to_yd($ud);
	return $$self - _reform($ud - $yday, 1);
}

sub tm
{
	my $self = shift;
	my ($day, $month, $year) = $self->day_month_year;
	my $wday = $self->weekday;
	my $yday = $self->yearday;
	return (0, 0, 0, $day, $month - 1, $year - 1900, $wday, $yday, undef);
}

########################################################################
# Private methods.

# Conversion to week, year.

sub _week_year
{
	my ($self, $wdo) = @_;
	my $ud = _unreform($$self);
	my ($year, $yday) = _day_to_yd($ud);
	my $yd = _reform($ud - $yday, 1);
	my $yoff = ($wdo - _day_to_weekday($yd)) % $days_in_week;
	$yday = $$self - $yd;
	return (int(($yday - $yoff + $days_in_week) / $days_in_week), $year);
}

# String representation of dates.
#
# We don't make any assumptions here.  For example, Europeans prefer
# dates as DD/MM/YYYY and the U.S.A. uses MM/DD/YYYY.  Each language has
# its own names for the months and days.  Therefore, every sub-class
# must override these methods.

sub _date_str_pref
{
	my $self = shift;
	my ($day, $month, $year) = @_ == 3 ? @_ : $self->day_month_year;
	die "must override";
}

sub _weekday_name_abbrev
{
	my $self = shift;
	my $wday = @_ ? $_[0] : $self->weekday;
	die "must override";
}

sub _weekday_name_full
{
	my $self = shift;
	my $wday = @_ ? $_[0] : $self->weekday;
	die "must override";
}

sub _month_name_abbrev
{
	my $self = shift;
	my $month = @_ ? $_[0] : ($self->day_month_year)[1];
	die "must override";
}

sub _month_name_full
{
	die "must override";
	my $self = shift;
	my $month = @_ ? $_[0] : ($self->day_month_year)[1];
}

# Formatting a date string.

sub _format_date_str
{
	my $self = shift;
	my $fmt = shift;
	my ($day, $month, $year);
	my $dmy = sub {
		($day, $month, $year) = $self->day_month_year if !defined $day;
	};
	my $s = '';
	while ($fmt =~ s/^(.*?)%([-_]?)(.)//o)
	{
		$s .= $1;
		my ($a, $b) = ($2, $3);
		my $f2 = '%'.{'' => '02', '-' => '', '_' => '2'}->{$a}.'u';
		my $f3 = '%'.{'' => '03', '-' => '', '_' => '3'}->{$a}.'u';
		my $f4 = '%'.{'' => '04', '-' => '', '_' => '4'}->{$a}.'u';
		my $f10 = '%'.{'' => '010', '-' => '', '_' => '10'}->{$a}.'u';
		if ($b eq '%') { $s .= '%'; }
		elsif ($b eq 'a') { &$dmy; $s .= $self->_weekday_name_abbrev; }
		elsif ($b eq 'A') { &$dmy; $s .= $self->_weekday_name_full; }
		elsif ($b eq 'b' || $b eq 'h') { &$dmy; $s .= $self->_month_name_abbrev($month); }
		elsif ($b eq 'B') { &$dmy; $s .= $self->_month_name_full($month); }
		elsif ($b eq 'd') { &$dmy; $s .= sprintf "$f2", $day; }
		elsif ($b eq 'D' || $b eq 'x') { &$dmy; $s .= $self->_date_str_pref($day, $month, $year); }
		elsif ($b eq 'e') { $s .= sprintf "$f10", $$self - $epoch_day; }
		elsif ($b eq 'j') { $s .= sprintf "$f3", $self->yearday; }
		elsif ($b eq 'm') { &$dmy; $s .= sprintf "$f2", $month; }
		elsif ($b eq 'n') { $s .= "\n"; }
		elsif ($b eq 'U') { $s .= sprintf "$f2", ($self->_week_year(0))[0]; }
		elsif ($b eq 'w') { $s .= sprintf "$f2", $self->weekday; }
		elsif ($b eq 'W') { $s .= sprintf "$f2", ($self->_week_year(1))[0]; }
		elsif ($b eq 'y') { &$dmy; $s .= sprintf "$f2", $year % 100; }
		elsif ($b eq 'Y') { &$dmy; $s .= sprintf "$f4", $year; }
	}
	$s .= $fmt;
	return $s;
}

# Parsing a date string.

sub _parse_day_month
{
	die "must override";
}

sub _parse_date
{
	my $self = shift;
	my $sr = shift;

	# Strip out hours, minutes, seconds and AM/PM, and timezone.
	$$sr =~ s/([01]\d|2[0-3]):([0-5]\d)(:([0-5]\d))?\s*([ap]m\b)?//io
		and $$sr =~ s/(?<!\d)[+-]\d{4}\b//o;

	# Year (four digits).
	my $y = $$sr =~ s/\b\d{4}\b//o ? $& + 0 : undef;

	# Day and month (names and/or numbers).
	my ($wd, $d, $m) = $self->_parse_day_month($sr);

	# Year (two digits)
	$y = $& + 1900 if !defined $y && $$sr =~ s/\b\d\d\b//o;

	return undef unless defined $d && defined $m & defined $y;
	my $day = _dmy_to_day($d, $m, $y);
	return undef unless defined $day;
	$day = _reform($day);
	return undef unless defined $day;
	return undef if defined $wd && $wd != _day_to_weekday($day);

	return $day;
}

########################################################################
# Internal calculation functions (not methods).

# Handling the Julian-to-Gregorian calendar reformation.
#
# From the cal(1) man page:
#
#    The Gregorian Reformation is assumed to have occurred in 1752 on
#    the 3rd of September.  By this time, most countries had recognized
#    the reformation (although a few did not recognize it until the
#    early 1900's).  Ten days following that date were eliminated by the
#    reformation, so the calendar for that month is a bit unusual.

my $reformation_year = 1752;
my $reformation_day1 = _dmy_to_day(3, 9, $reformation_year);
my $reformation_days_skipped = 11;

# Apply the reformation to a number of days since the epoch.  In normal
# operation, return undef if we are passed a day that was eliminated by
# the reformation.  If the nogaps param is set, then instead map all
# eliminated days to the first following valid day.

sub _reform
{
	my ($day, $nogaps) = @_;
	return $day if $day < $reformation_day1;
	return $nogaps ? $reformation_day1 : undef
		if $day < $reformation_day1 + $reformation_days_skipped;
	return $day - $reformation_days_skipped;
}

sub _unreform
{
	my $day = shift;
	return $day if $day < $reformation_day1;
	return $day + $reformation_days_skipped;
}

# The treatment of leap years also changed at the reformation, so this
# method is part of the reformation definition.

sub _is_leap
{
	my $year = shift;
	if ($year >= $reformation_year)
	{
		return 1 if $year % 400 == 0;
		return 0 if $year % 100 == 0;
	}
	return 1 if $year % 4 == 0;
	return 0;
}

# A table used for optimizing.

my @yeardays = (
	[ 2040, _dmy_to_day(1, 1, 2040) ],
	[ 2030, _dmy_to_day(1, 1, 2030) ],
	[ 2020, _dmy_to_day(1, 1, 2020) ],
	[ 2010, _dmy_to_day(1, 1, 2010) ],
	[ 2000, _dmy_to_day(1, 1, 2000) ],
	[ 1990, _dmy_to_day(1, 1, 1990) ],
	[ 1980, _dmy_to_day(1, 1, 1980) ],
	[ 1970, _dmy_to_day(1, 1, 1970) ],
	[ 1900, _dmy_to_day(1, 1, 1900) ],
);

# None of the following know anything about the reformation, so they
# only operate in the "unreformed" days-since-epoch domain, or, in other
# words, a calendar that includes the days erased by the reformation.

sub _days_in_century
{
	my $year = shift;
	return	  $days_in_non_leap_century
		+ _is_leap(int(($year + 99) / 100) * 100);
}

sub _days_in_year
{
	return $days_in_non_leap_year + _is_leap(shift);
}

sub _months_to_my
{
	my $m = shift;
	return ( 	$m % $months_in_year + $month_min,
			int($m / $months_in_year) + $year_min
		);
}

sub _days_in_month
{
	my ($month, $year) = @_;
	return undef if $month < $month_min || $month > $month_max;
	my $m = $month - $month_min;
	return	  (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[$m]
		+ ($m == 1 ? _is_leap($year) : 0);
}

sub _dmy_to_day
{
	my ($day, $month, $year) = @_;
	my $diy = _year_to_day($year);
	return undef unless defined $diy;
	my $dim = _days_before_month($month, $year);
	return undef unless defined $dim;
	my $did = _days_before_day($day, $month, $year);
	return undef unless defined $did;
	return $diy + $dim + $did;
}

sub _dm_to_day
{
	return _dmy_to_day($_[0], _months_to_my($_[1]));
}

sub _tm_to_day
{
	return _dmy_to_day($_[3], $_[4] + 1, $_[5] + 1900);
}

sub _year_to_day
{
	my $year = shift;
	return undef if $year < $year_min || $year > $year_max;
	my $y = $year_min;
	my $days = $epoch_day;
	for my $yd (@yeardays)
	{
		if ($year >= $yd->[0])
		{
			$y = $yd->[0];
			$days = $yd->[1];
			last;
		}
	}
	while ($y < $year)
	{
		if ($year - $y >= 100)
		{
			$days += _days_in_century($y);
			$y += 100;
		}
		else
		{
			$days += _days_in_year($y);
			$y++;
		}
	}
	return $days;
}

sub _days_before_month
{
	my ($month, $year) = @_;
	return undef if $month < $month_min || $month > $month_max;
	my $m = $month - $month_min;
	return	  (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)[$m]
		+ ($m > 1 ? _is_leap($year) : 0);
}

sub _days_before_day
{
	my ($day, $month, $year) = @_;
	return undef if	   $day < $day_min
			|| $day >= $day_min + _days_in_month($month, $year);
	return $day - $day_min;
}

sub _day_to_yd
{
	my $d = shift;
	my $year = $year_min;
	my $day = $epoch_day;
	# Optimization.
	for my $yd (@yeardays)
	{
		if ($d >= $yd->[1])
		{
			$year = $yd->[0];
			$day = $yd->[1];
			last;
		}
	}
	while ($day < $d)
	{
		my $n;
		if ($d - $day >= ($n = _days_in_century($year)))
		{
			$day += $n;
			$year += 100;
		}
		elsif ($d - $day >= ($n = _days_in_year($year)))
		{
			$day += $n;
			$year++;
		}
		else
		{
			last;
		}
	}
	return ($year, $d - $day);
}

sub _day_to_dmy
{
	my $d = shift;
	my ($month, $year) = ($month_min);
	($year, $d) = _day_to_yd($d);
	my $n;
	while ($d >= ($n = _days_in_month($month, $year)))
	{
		$d -= $n;
		$month++;
	}
	return ($day_min + $d, $month, $year);
}

sub _day_to_dm
{
	my ($day, $month, $year) = _day_to_dmy(shift);
	return ($day, ($year - $year_min) * $months_in_year + $month - $month_min);
}

# The following functions deal with days of the week, so they only
# operate in the "reformed" days-since-epoch domain, or, in other words,
# a calendar that does not include the days erased by the reformation.

sub _day_to_weekday
{
	return (shift() - $epoch_day + $epoch_weekday) % $days_in_week;
}

1;
