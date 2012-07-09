package ABO::DestroyCallback;
use feature 'unicode_strings';

# This object simply executes a function when it is destroyed.

use Carp qw(confess);

sub new
{
	my ($class, $func) = @_;
	confess "bad arg" unless ref($func) eq 'CODE';
	bless \$func, ref($class) || $class;
}

sub DESTROY
{
	my $self = shift;
	&$$self;
	undef $$self;
}

package ABO::Error;

# Uniform error reporting.
#
# The ABO nucleus contains a reference to one of these objects,
# initialised when the nucleus is started.  All calls to the 'error'
# method of the ABO::Base class end up going through here.

use Carp qw(croak confess);

sub init
{
	my $self = shift;
	confess "bad arg" unless @_ == 1 && ref($_[0]) eq 'CODE';
	$self->{'efstack'} = [];
	$self->{'pushed'} = [];
	$self->push_error_func(shift());
	return $self;
}

sub fork
{
	my $self = shift;
	my $new = bless {}, ref($self);
	$new->{'efstack'} = [];
	$new->{'pushed'} = [];
	$new->push_error_func(sub { $self->error(@_) });
	return $new;
}

sub error
{
	my $self = shift;
	my $efstack = $self->{'efstack'};
	my $elevel = $self->{'error_level'};
	my $nlevel = defined($elevel) ? $elevel - 1 : $#$efstack;
	my $efunc;
	$nlevel-- until $nlevel < 0 || defined($efunc = $efstack->[$nlevel]);
	croak @_ unless defined $efunc;
	local $self->{'error_level'} = $nlevel;
	&$efunc(@_);
}

sub scope_error_func
{
	my $self = shift;
	confess "bad arg" unless @_ == 1 && ref($_[0]) eq 'CODE';
	my $efstack = $self->{'efstack'};
	push @$efstack, shift;
	my $pos = $#$efstack;
	return ABO::DestroyCallback->new(sub {
		undef $efstack->[$pos];
		$#$efstack-- until !@$efstack || defined $efstack->[$#$efstack];
	});
}

sub scope_error_prefix
{
	my $self = shift;
	my $prefix = shift;
	return $self->scope_error_func(sub { $self->error($prefix, @_) });
}

sub push_error_func
{
	my $self = shift;
	push @{$self->{'pushed'}}, $self->scope_error_func(@_);
	return $self;
}

sub push_error_prefix
{
	my $self = shift;
	push @{$self->{'pushed'}}, $self->scope_error_prefix(@_);
	return $self;
}

sub pop_error
{
	my $self = shift;
	pop @{$self->{'pushed'}};
	return $self;
}

1;
