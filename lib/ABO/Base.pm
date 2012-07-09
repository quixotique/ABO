package ABO::Base;

use ABO::Nucleus;
use Carp;

sub new
{
	confess "don't use new";
}

sub init
{
	confess "must override init";
}

# Create a new ABO object.

sub make
{
	my $self = shift;
	# We use a goto-&NAME form instead of the more correct method call:
	#	$self->_nucleus->make(@_);
	# mainly to cut down the size of stack traces.
	unshift @_, $self->_nucleus;
	goto &ABO::Nucleus::make;
}

# Clone an ABO object (deep copy).

sub clone
{
	my $self = shift;
	my $clone = bless {}, ref($self);
	$clone->_set_nucleus($self->_nucleus);
	return $clone;
}

# Create an ABO::Currency object with the configured currency code.

sub make_money
{
	my $self = shift;
	$self->_nucleus->make_money(@_);
}

# Create an ABO::Date object in the configured date language.

sub make_date
{
	my $self = shift;
	$self->_nucleus->make_date(@_);
}

# Various universally-useful error reporting tools.

sub error		{ shift->_nucleus->error_reporter->error(@_); }
sub blah		{ shift->_nucleus->option('verbose') and print STDERR @_, "\n"; }
sub scope_error_func	{ shift->_nucleus->error_reporter->scope_error_func(@_); }
sub push_error_func	{ shift->_nucleus->error_reporter->push_error_func(@_); }
sub scope_error_prefix	{ shift->_nucleus->error_reporter->scope_error_prefix(@_); }
sub push_error_prefix	{ shift->_nucleus->error_reporter->push_error_prefix(@_); }

sub _nucleus
{
	$_[0]->{__PACKAGE__.'.nucleus'};
}

sub _config
{
	$_[0]->_nucleus->config;
}

sub _set_nucleus
{
	my $self = shift;
	confess "bad arg" unless @_ == 1 && UNIVERSAL::isa($_[0], ABO::Nucleus);
	return $self->{__PACKAGE__.'.nucleus'} = shift;
}

sub _fork_nucleus
{
	my $self = shift;
	return $self->_set_nucleus($self->_nucleus->fork);
}

1;
