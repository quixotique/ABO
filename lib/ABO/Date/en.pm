package ABO::Date::en;

use ABO::Date::_gregorian;
@ISA = qw(
	ABO::Date::_gregorian
);

use strict;

my @mn = (
		'January', 'February', 'March', 'April',
		'May', 'June', 'July', 'August',
		'September', 'October', 'November', 'December'
	);
my %mn = (	'jan' => 1, 'feb' => 2, 'mar' => 3, 'apr' => 4,
		'may' => 5, 'jun' => 6, 'jul' => 7, 'aug' => 8,
		'sep' => 9, 'oct' => 10, 'nov' => 11, 'dec' => 12
	);
my @wn = (
		'Sunday', 
		'Monday', 'Tuesday', 'Wednesday',
		'Thursday', 'Friday', 'Saturday',
	);
my %wn = (
		'sun' => 0, 
		'mon' => 1, 'tue' => 2, 'wed' => 3,
		'thu' => 4, 'fri' => 5, 'sat' => 6,
	);

# Private methods.

sub _date_str_pref
{
	my $self = shift;
	my ($day, $month, $year) = @_ == 3 ? @_ : $self->day_month_year;
	return sprintf '%02u/%02u/%04u', $day, $month, $year;
}

sub _weekday_name_abbrev
{
	my $self = shift;
	return substr $self->_weekday_name_full(@_), 0, 3;
}

sub _weekday_name_full
{
	my $self = shift;
	my $wday = @_ ? $_[0] : $self->weekday;
	return $wn[$wday];
}

sub _month_name_abbrev
{
	my $self = shift;
	return substr $self->_month_name_full(@_), 0, 3;
}

sub _month_name_full
{
	my $self = shift;
	my $month = @_ ? $_[0] : ($self->day_month_year)[1];
	return $mn[$month - 1];
}

sub _parse_day_month
{
	my $self = shift;
	my $sr = shift;
	my ($wday, $day, $month);

	my $wnp = join '|', keys %wn;
	$wday = $wn{lc $1} if $$sr =~ s/\b($wnp).*?\b//io;
	$day = $& + 0 if $$sr =~ s/\b\d{1,2}(?!\d)//o;

	my $mnp = join '|', keys %mn;
	$month = $mn{lc $1} if $$sr =~ s/\b($mnp).*?\b//io;
	$month = $& + 0 if !defined $month && $$sr =~ s/\b\d{1,2}(?!\d)//o;

	return ($wday, $day, $month);
}

1;
