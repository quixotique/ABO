package ABO::Currency::AUD;

use ABO::Currency;
@ISA = qw(
	ABO::Currency
);

use Carp qw(carp cluck);
use POSIX qw(floor);
use strict;

sub _convert
{
	my ($self, $val) = @_;
	if (!defined $val)
	{
		cluck "Use of uninitialized value";
		return 0;
	}
	$val =~ s/,//og;
	floor($val * 100 + .5);
}

sub _normalize
{
	my $self = shift;
	$$self = floor($$self + .5);
	$self;
}

sub as_number
{
	my $self = shift;
	return $$self / 100;
}

sub as_string
{
	my $self = shift;
	return '0.00' if $$self == 0;
	my $r = sprintf '%.2f', $$self / 100;
	1 while $r =~ s/(\d)(\d\d\d)(?=\D)/$1,$2/o;
	$r;
}

1;
