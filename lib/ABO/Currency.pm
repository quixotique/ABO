package ABO::Currency;
use feature 'unicode_strings';

use strict;

use vars qw($VERSION);
$VERSION = "1.00";

my %implements;  # mapping from currency name to implementor class

use Carp qw(carp);

use overload (
	'bool'	=> "as_bool",
	'+0'	=> "as_number",
	'""'	=> "as_string",
	'neg'	=> "negate",
	'+'	=> "add",
	'-'	=> "subtract",
	'*'	=> "multiply",
	'/'	=> "divide",
	'+='	=> "add_to",
	'-='	=> "subtract_from",
	'*='	=> "multiply_by",
	'/='	=> "divide_by",
	'<=>'	=> "num_compare",
	fallback => 1,
);

use vars qw($default_code);

sub new
{
	my ($class, $amount, $code) = @_;
	return $amount->clone if UNIVERSAL::isa($amount, __PACKAGE__);
	$code = $code || $default_code or
		Carp::croak "no currency defined";
	my $impclass = implementor($code) or
		Carp::croak "unsupported currency `$code'";
	return $impclass->_init($amount, $code);
}

sub _init
{
	my $class = shift;
	my $val = $class->_convert(shift);
	bless \$val, $class;
}

sub implementor
{
    my ($code, $impclass) = @_;

    if ($impclass) {
	# Set the implementor class for a given code
        my $old = $implements{$code};
        $impclass->_init_implementor($code);
        $implements{$code} = $impclass;
        return $old;
    }

    my $ic = $implements{$code};
    return $ic if $ic;

    # code not yet known, look for internal or
    # preloaded (with 'use') implementation
    $ic = "ABO::Currency::$code";  # default location

    no strict 'refs';
    # check we actually have one for the code:
    unless (defined @{"${ic}::ISA"}) {
        # Try to load it
        eval "require $ic";
        die $@ if $@ && $@ !~ /Can\'t locate.*in \@INC/o;
        return unless defined @{"${ic}::ISA"};
    }

    $ic->_init_implementor($code);
    $implements{$code} = $ic;
    $ic;
}


sub _init_implementor
{
	my($class, $code) = @_;
	# Remember that one implementor class may actually
	# serve to implement several currencies.
}


sub clone
{
	my $self = shift;
	my $other = $$self;
	bless \$other, ref $self;
}

sub code
{
	my $self = shift;
	return $1 if ref($self) =~ /ABO::Currency::([A-Z]{3})$/o;
	die "code not implemented";
}

sub _convert
{
	my $self = shift;
	carp "Use of uninitialized value" if !defined $_[0];
	$_[0] + 0;
}

sub _normalize
{
	my $self = shift;
	$self;
}

sub as_bool
{
	my $self = shift;
	$$self != 0;
}

sub as_number
{
	my $self = shift;
	$$self + 0;
}

sub as_string
{
	my $self = shift;
	"$$self";
}

sub negate
{
	my ($self) = @_;
	my $r = $self->clone;
	$$r = -$$r;
	$r;
}

sub add
{
	my ($self, $n) = @_;
	my $r = $self->clone;
	$$r += ref($n) eq ref($self) ? $$n : $self->_convert($n);
	$r->_normalize;
}

sub subtract
{
	my ($self, $n, $rev) = @_;
	my $r = $self->clone;
	$$r -= ref($n) eq ref($self) ? $$n : $self->_convert($n);
	$$r = -$$r if $rev;
	$r->_normalize;
}

sub multiply
{
	my ($self, $n) = @_;
	my $r = $self->clone;
	my $nv = ref($n) eq ref($self) ? $n->as_number : $n + 0;
	$$r = $$r * $nv;
	$r->_normalize;
}

sub divide
{
	my ($self, $n, $rev) = @_;
	if ($rev)
	{
		# Currency / Currency -> number
		my $nv = ref($n) eq ref($self) ? $n->as_number : $self->_convert($n);
		return $nv / $self->as_number;
	}
	elsif (ref($n) eq ref($self))
	{
		# Currency / Currency -> number
		return $self->as_number / $n->as_number;
	}
	# Currency / number -> Currency
	my $r = $self->clone;
	$$r /= $n + 0;
	$r->_normalize;
}

sub add_to
{
	my ($self, $n) = @_;
	$$self += ref($n) eq ref($self) ? $$n : $self->_convert($n);
	$self->_normalize;
}

sub subtract_from
{
	my ($self, $n) = @_;
	$$self -= ref($n) eq ref($self) ? $$n : $self->_convert($n);
	$self->_normalize;
}

sub multiply_by
{
	my ($self, $n) = @_;
	$$self *= ref($n) eq ref($self) ? $n->as_number : $n + 0;
	$self->_normalize;
}

sub divide_by
{
	my ($self, $n) = @_;
	$$self /= ref($n) eq ref($self) ? $n->as_number : $n + 0;
	$self->_normalize;
}

sub num_compare
{
	my ($self, $n, $rev) = @_;
	my $r = $$self <=> (ref($n) eq ref($self) ? $$n : $self->_convert($n));
	return $rev ? -$r : $r;
}

1;

__END__

=head1 NAME

ABO::Currency -- financial currency type

=head1 SYNOPSIS

 $a1 = ABO::Currency->new(452.4);
 $a2 = ABO::Currency->new(15, 'AUD');
 $a3 = $u2->clone;

 $str = $a->as_string;
 $str = "$a";

 $code = $a->code;

=head1 DESCRIPTION

This module implements the C<ABO::Currency> class.  An objects of this class
represents a single amount in a given currency.

=head1 CONSTRUCTORS

The following methods to construct new C<ABO::Currency> objects are provided:

=over 4

=item $amt = ABO::Currency->new( $amount, [$code] )

This class method constructs a new ABO::Currency object.  The numerical
or string representation of an amount is given as argument
together with an optional currency code;

The constructor will map this to an appropriate
ABO::Currency subclass, construct a new object of this class and return it.

=item $amt->clone

This method returns a copy of the $amount.

=back

=head1 COMMON METHODS

The methods described in this section are available for all C<ABO::Currency>
objects.

The common methods are:

=over 4

=item $amt->code

This method will return the three-letter code of the currency in which
the amount is represented.

=item $amt->as_string

This method converts an ABO::Currency object to a plain string, formatted
according to the currency's conventions.
ABO::Currency objects are also converted to plain strings automatically
by overloading.  It means that $amt objects can be used as plain strings
in most Perl constructs.

=back

=head1 SEE ALSO

L<ABO::Currency::AUD>

=head1 COPYRIGHT

Copyright 1999 Headroom Engineering Pty Limited.

=head1 AUTHORS

C<ABO::Currency> was developed by Andrew Bettison.

=cut
