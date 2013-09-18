package ABO::Date;
use feature 'unicode_strings';

use strict;

use vars qw($VERSION);
$VERSION = "1.00";

use Carp;

use overload (
	'bool'	=> "as_bool",
	'0+'	=> "as_number",
	'""'	=> "as_string",
	'~'	=> "as_number",
	'neg'	=> "_o_negate",
	'+'	=> "_o_add",
	'-'	=> "_o_subtract",
	'*'	=> "_o_multiply",
	'/'	=> "_o_divide",
	'+='	=> "_o_add_to",
	'-='	=> "_o_subtract_from",
	'*='	=> "_o_multiply_by",
	'/='	=> "_o_divide_by",
	'<=>'	=> "_o_ncmp",
	'eq'	=> "_o_seq",
	'ne'	=> "_o_sne",
	'cmp'	=> "_o_scmp",
	fallback => 1,
);

use vars qw($default_lang);
my %implements;  # mapping from date language to implementor class

sub new
{
	my ($class, $date, $lang) = @_;
	Carp::croak "undefined date argument" unless defined $date;
	if ($date eq '.')
	{
		my $val;
		return bless \$val, $class;
	}
	$lang = $lang || $default_lang or
		Carp::croak "no date language defined";
	my $impclass = implementor($lang) or
		Carp::croak "unsupported date language `$lang'";
	return $impclass->_init($date, $lang);
}

sub _init
{
	my $class = shift;
	my ($date, $lang) = @_;
	return $date->clone if UNIVERSAL::isa($date, $class);
	my $val = !ref $date && $date =~ /^D=(\d+)$/o ? $1 + 0
		: $class->_convert(@_);
	return undef unless defined $val;
	bless \$val, $class;
}

sub implementor
{
    my ($lang, $impclass) = @_;

    if ($impclass) {
	# Set the implementor class for a given lang
        my $old = $implements{$lang};
        $impclass->_init_implementor($lang);
        $implements{$lang} = $impclass;
        return $old;
    }

    my $ic = $implements{$lang};
    return $ic if $ic;

    # lang not yet known, look for internal or
    # preloaded (with 'use') implementation
    $ic = "ABO::Date::$lang";  # default location

    no strict 'refs';
    # check we actually have one for the lang:
    unless (@{"${ic}::ISA"}) {
        # Try to load it
        eval "require $ic";
        die $@ if $@ && $@ !~ /Can\'t locate.*in \@INC/o;
        return unless @{"${ic}::ISA"};
    }

    $ic->_init_implementor($lang);
    $implements{$lang} = $ic;
    $ic;
}


sub _init_implementor
{
	my ($class, $lang) = @_;
	# Remember that one implementor class may actually
	# serve to implement several languages.
}

sub serialize
{
	my $self = shift;
	"D=$$self";
}

sub clone
{
	my $self = shift;
	my $other = $$self;
	bless \$other, ref $self;
}

sub lang
{
	my $self = shift;
	return $1 if ref($self) =~ /ABO::Date::(\w+)$/o;
	die "lang not implemented";
}

sub _convert		{ die "not implemented"; }

# These methods are overridden in all sub-classes.  These values are for
# the year "dot".

sub format		{ '.' }
sub day_month_year	{ () }
sub day			{ undef }
sub month		{ undef }
sub year		{ undef }
sub weekday		{ undef }
sub yearday		{ undef }
sub tm			{ () }

# Overload methods.

sub as_bool
{
	1;
}

sub as_number
{
	my $self = shift;
	defined $$self ? $$self + 0 : undef;
}

sub as_string
{
	shift->format('%x');
}

sub _o_negate
{
	Carp::croak "cannot negate a date";
}

sub _o_add
{
	my ($self, $n) = @_;
	Carp::croak "cannot add to year dot" unless defined $$self;
	Carp::croak "cannot add two dates" if UNIVERSAL::isa($n, __PACKAGE__);
	my $r = $self->clone;
	$$r += $n;
	$r;
}

sub _o_subtract
{
	my ($self, $n, $rev) = @_;
	Carp::croak "cannot subtract from year dot" unless defined $$self;
	return $rev ? $$n - $$self : $$self - $$n if UNIVERSAL::isa($n, __PACKAGE__);
	my $r = $self->clone;
	$$r = $rev ? $n - $$r : $$r - $n;
	Carp::croak "date before epoch" if $$r <= 0;
	$r;
}

sub _o_multiply
{
	Carp::croak "cannot multiply dates";
}

sub _o_divide
{
	Carp::croak "cannot divide dates";
}

sub _o_add_to
{
	my ($self, $n) = @_;
	Carp::croak "cannot modify year dot" unless defined $$self;
	Carp::croak "cannot add two dates" if UNIVERSAL::isa($n, __PACKAGE__);
	$$self += $n + 0;
	$self;
}

sub _o_subtract_from
{
	my ($self, $n) = @_;
	Carp::croak "cannot modify year dot" unless defined $$self;
	Carp::croak "cannot subtract a date from a date" if UNIVERSAL::isa($n, __PACKAGE__);
	$$self -= $n + 0;
	Carp::croak "date before epoch" if $$self <= 0;
	$self;
}

sub _o_multiply_by
{
	Carp::croak "cannot multiply dates";
}

sub _o_divide_by
{
	Carp::croak "cannot divide dates";
}

sub _o_ncmp
{
	my ($self, $n, $rev) = @_;
	Carp::croak "can only compare a date with another date"
		unless UNIVERSAL::isa($n, __PACKAGE__);
	return $rev ? $$n <=> $$self : $$self <=> $$n if defined $$self && defined $$n;
	return $rev ? -1 : 1 if defined $$self;
	return $rev ? 1 : -1 if defined $$n;
	return 0;
}

sub _o_seq
{
	my ($self, $s) = @_;
	return !defined $$self if $s eq '.';
	!$self->scmp($s);
}

sub _o_sne
{
	my ($self, $s) = @_;
	return defined $$self if $s eq '.';
	!!$self->scmp($s);
}

sub _o_scmp
{
	Carp::croak "string comparison of dates not supported";
}

1;

__END__

=head1 NAME

ABO::Date -- date type

=head1 SYNOPSIS

 $d1 = ABO::Date->new('15/2/2002');
 $d2 = ABO::Date->new('30/6/98', 'en');
 $d3 = $u2->clone;

 $str = $d->as_string;
 $str = "$d";

 $lang = $a->lang;

=head1 DESCRIPTION

This module implements the C<ABO::Date> class.  An objects of this class
represents a single date in a given language.

=head1 CONSTRUCTORS

The following methods to construct new C<ABO::Date> objects are provided:

=over 4

=item $date = ABO::Date->new( $datestr [, $lang] )

This class method constructs a new ABO::Date object.  The string
representation of a date is given as argument together with an optional
language;

The constructor will map this to an appropriate ABO::Date subclass,
construct a new object of this class and return it.

=item $date->clone

This method returns a copy of the $date.

=back

=head1 COMMON METHODS

The methods described in this section are available for all C<ABO::Date>
objects.

The common methods are:

=over 4

=item $date->lang

This method will return the language in which the date is represented.
The langage is an identifier that can be used as a Perl package name
(without "::"), typically following the convention used in naming
locales, i.e., a two-letter, lowercase ISO-3166 language code,
optionally followed by an underscore "_" and a two-letter, uppercase
ISO-639 country code, e.g., "en", "en_US", "en_AU".

=item $date->as_string

This method converts an ABO::Date object to a plain string, formatted
according to the date's language.  ABO::Date objects are also converted
to plain strings automatically by overloading.  It means that $date
objects can be used as plain strings in most Perl constructs.

=back

=head1 SEE ALSO

L<ABO::Date::en>

=head1 COPYRIGHT

Copyright 2001 Headroom Engineering Pty Limited.

=head1 AUTHORS

C<ABO::Date> was developed by Andrew Bettison.

=cut
