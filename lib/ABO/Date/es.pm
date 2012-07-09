package ABO::Date::es;

use ABO::Date::_gregorian;
@ISA = qw(
	ABO::Date::_gregorian
);

use strict;

my @mn = (
		'enero', 'febrero', 'marzo', 'abril',
		'mayo', 'junio', 'julio', 'agosto',
		'septiembre', 'octubre', 'noviembre', 'diciembre'
	);
my %mn = (	'ene' => 1, 'feb' => 2, 'mar' => 3, 'apr' => 4,
		'may' => 5, 'jun' => 6, 'jul' => 7, 'ago' => 8,
		'sep' => 9, 'oct' => 10, 'nov' => 11, 'dec' => 12
	);
my @wna = (
		'D', 
		'L', 'M', 'X',
		'J', 'V', 'S',
	);
my @wnf = (
		'domingo', 
		'lunes', 'martes', 'miércoles',
		'jueves', 'viernes', 'sábado',
	);
my %wn = (
		'domingo' => 0, 'domíngo' => 0, 'domÍngo' => 0, 
		'lunes' => 1, 'martes' => 2,
		'miercoles' => 3, 'miércoles' => 3, 'miÉrcoles' => 3,
		'jueves' => 4, 'viernes' => 5,
		'sabado' => 6, 'sábado' => 6, 'sÁbado' => 6,
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
	my $wday = @_ ? $_[0] : $self->weekday;
	return $wna[$wday];
}

sub _weekday_name_full
{
	my $self = shift;
	my $wday = @_ ? $_[0] : $self->weekday;
	return $wnf[$wday];
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
	$wday = $wn{lc $1} if $$sr =~ s/\b($wnp)\b//io;
	$day = $& + 0 if $$sr =~ s/\b\d{1,2}(?!\d)//o;

	my $mnp = join '|', keys %mn;
	$month = $mn{lc $1} if $$sr =~ s/\b($mnp).*?\b//io;
	$month = $& + 0 if !defined $month && $$sr =~ s/\b\d{1,2}(?!\d)//o;
	return ($wday, $day, $month);
}

1;
