package ABO::Currency::ESP;

use ABO::Currency;
@ISA = qw(
	ABO::Currency
);

use strict;

sub _convert
{
	my $self = shift;
	my $val = shift;
	$val =~ s/\.//og;
	$val =~ s/,/./o;
	floor($val + .5);
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
	return $$self;
}

sub as_string
{
	my $self = shift;
	my $r = $$self;
	return '0' if $r == 0;
	1 while $r =~ s/(\d)(\d\d\d)\b/$1.$2/o;
	"$r";
}

1;
