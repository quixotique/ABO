package ABO::Currency::BB;

use ABO::Currency;
@ISA = qw(
	ABO::Currency
);

use strict;

sub _convert
{
    my $self = shift;
    my $val = shift;
    $val =~ s/,//og;
    sprintf('%.0f', $val) + 0;
}

sub as_number
{
	my $self = shift;
	return $$self;
}

sub as_string
{
	my $self = shift;
	return '0' if $$self == 0;
	my $r = "$$self";
	1 while $r =~ s/(\d)(\d\d\d)(?=\D|$)/$1,$2/o;
	$r;
}

1;
