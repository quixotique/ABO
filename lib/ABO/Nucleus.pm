package ABO::Nucleus;

# Most objects in the ABO universe carry a reference to one of these
# "nucleus" objects.  This is how the ABO configuration, error reporter,
# run-time options, and various other common services and settings get
# propagated through the ABO system without having to explicitly pass
# them to constructors all the time, which would be tedious in the
# extreme and furthermore unmaintainable.
#
# To see how the nucleus gets passed from object to object, see the
# "make" method.

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use ABO::Currency;
use ABO::Date;

use Carp qw(confess);

##############################################
# Nucleus object constructor.

# The first nucleus object is created with the "new" method.  All others
# after that are created by forking.

sub new
{
	my $self = bless {}, shift;
	$self->_set_nucleus($self);
	$self->{'options'} = {};
	return $self;
}

# The nucleus object can be "forked", which is effectively a shallow
# copy -- a new nucleus object is created, but any objects that it
# references are not copied, so the forked nucleus shares the same
# objects with the original.  Some or all of the fork's elements can
# then be changed at will, to propagate different global behaviours
# (configuration, options, factories, etc.) through separate sub-parts
# of the application.

sub fork
{
	my $self = shift;
	my %fork = %$self;
	my $fork = bless \%fork, ref($self);
	$fork->_set_nucleus($fork);
	return $fork;
}

##############################################
# Generic ABO object constructor.

# Most classes in the ABO universe are sub-classes of the ABO::Base
# class, and their objects are created using this "make" method, which:
#
# (a) loads the package if not already loaded; this permits lazy loading
# analogous to the standard Perl SelfLoader, to avoid compilation of
# unwanted packages;
#
# (b) creates and blesses a new anonymous hash (all ABO::Base objects
# are anonymous hashes);
#
# (c) propagates a reference to the Nucleus object; and
#
# (d) calls the optional constructor "init" on the new object.
#
# Objects which are not sub-classes of ABO::Base are normally created by
# calling the "new" method, following the Perl convention.  This "make"
# method does not know how to do that, so it cannot be used to create
# such objects.  However, objects which are not sub-classes of ABO::Base
# but (a) use a blessed anonymous hash, and (b) have a constructor
# called "init", can be created with this "make" method.

my %loaded;

sub make
{
	my $self = shift;
	my $class = shift;
	if (!$loaded{$class})
	{
		$self->blah("load $class");
		eval "require $class";
		Carp::croak $@ if $@;
		$loaded{$class} = 1;
	}
	my $obj = bless {}, ref($class) || $class;
	$obj->_set_nucleus($self) if $obj->isa(ABO::Base);
	if (my $mref = $obj->can('init')) {
		$obj = $obj->$mref(@_);
	}

	return $obj;
}

##############################################
# Configuration.

# The ABO system is configured through a variety of configuration files.
# The ABO::Config package knows how to locate and parse these files, and
# provides access to the resulting values through a few, simple methods.
#
# A single ABO::Config object is created and initialised on ABO startup,
# and the first nucleus object is given a reference to it through this
# "set_config" method.  Thereafter, all forks of the nucleus will share
# a reference to that object, thereby making the configuration available
# to all ABO objects through their nucleus.
#
# Some ABO objects have their own, private configuration files (for
# example, each ABO::Book object), whose settings are confined to that
# object and all objects created by it.  In this case, the object forks
# the nucleus, then forks the ABO::Config object using the "fork_config"
# method here, then instructs the forked copy to incorporate additional
# configuration files.

sub config		{ $_[0]->{'config'}; }

sub set_config
{
	my $self = shift;
	confess "bad arg" unless UNIVERSAL::isa($_[0], ABO::Config);
	return $self->{'config'} = shift;
}

sub fork_config
{
	my $self = shift;
	my $config = $self->config->clone;
	$config->_set_nucleus($self);
	return $self->set_config($config);
}

##############################################
# Run-time options.

# This is a simple list of named values that allow settings that are
# independent of the configuration system to be broadcast to all ABO
# objects.

sub option		{ $_[0]->{'options'}->{$_[1]}; }

sub set_option
{
	my ($self, $opt, $val) = @_;
	$self->{'options'}->{$opt} = $val;
	return $self;
}

##############################################
# Account list.

# An awful lot of ABO objects need access to the chart of accounts.
# Each nucleus contains a reference to the ABO::AccountList object that
# is initialised at ABO startup.

sub account_list	{ $_[0]->{'account_list'}; }

sub set_account_list
{
	my $self = shift;
	confess "bad arg" unless UNIVERSAL::isa($_[0], ABO::AccountList);
	return $self->{'account_list'} = shift;
}

##############################################
# Error reporter.

# Perl's support for exceptions is a bit patchy (the thrown exception is
# always a string, and there is no "try...catch" syntax like Java's), so
# the ABO package uses a different approach to dealing with failures.
#
# In general, if a failure is caused by an internal programming error
# (such as passing illegal arguments between ABO objects, or a failed
# assertion) then ABO bails out using 'die', 'Carp::croak', or
# 'Carp::confess'.
#
# In all other cases (such as invalid user input, corruption of data
# recovered from disk, or invalid arguments passed in from outside ABO),
# a verbose, informative, diagnostic message (in English) is output at
# the point where the error is detected, and the method returns a result
# indicating failure, allowing methods to exit voluntarily up to a level
# where the failure can be accommodated.
#
# The output of the diagnostic message is performed using the ABO::Error
# error-reporting object that is initialised at ABO startup.  This
# allows the code that invokes ABO to handle the messages as it sees fit
# (in a typical command-line utility they are output to STDERR, prefixed
# with the name of the program, but in a GUI invironment for example,
# they might result in a pop-up dialog, or displayed in a scrolling
# "progress" window).
#
# A lot of cleverness goes on in ABO::Error to compensate for the
# inability in Perl to catch an exception and re-throw it with some
# extra information aggregated, or in another form.

sub error_reporter	{ $_[0]->{'error_reporter'}; }

sub set_error_reporter
{
	my $self = shift;
	confess "bad arg" unless UNIVERSAL::isa($_[0], ABO::Error);
	return $self->{'error_reporter'} = shift;
}

sub fork_error_reporter
{
	my $self = shift;
	return $self->set_error_reporter($self->error_reporter->fork);
}

##############################################
# Transaction validator.

# This is a piece of information that the nucleus carries to the
# constructor of ABO::Transaction, which uses it to perform a final
# validity check of each transaction object created, before returning.
# This allows any ABO object to place any restriction on the
# transactions that it can produce, effectively acting as a guarantee
# that its transactions conform.
#
# This could also have been done by performing the same check on all
# transactions in the object itself, before returning them, but by then
# the context of origin of the transaction is lost, so the diagnostic
# message would be useless to the user, who wants to know exactly what
# piece of input provoked the problem.

sub transaction_validator
{
	$_[0]->{'transaction_validator'} or sub { 1 };
}

sub set_transaction_validator
{
	my $self = shift;
	confess "bad arg" unless ref($_[0]) eq 'CODE';
	return $self->{'transaction_validator'} = shift;
}

sub validate_transaction
{
	my $self = shift;
	confess "bad arg" unless UNIVERSAL::isa($_[0], ABO::Transaction);
	return &{$self->transaction_validator}(shift);
}

##############################################
# Time services, to make all "now" and "epoch" calculations uniform in
# the same process.

sub now
{
	my $self = shift;
	return $self->{'now'} if defined $self{'now'};
	return $self->{'now'} = time;
}

sub today
{
	my $self = shift;
	return $self->{'today'} if defined $self{'today'};
	return $self->{'today'} = $self->make_date([localtime $self->now]);
}

sub epoch
{
	my $self = shift;
	return $self->{'epoch'} if defined $self{'epoch'};
	my $edate = $self->_config->var_date('epoch') or die;
	$self->error("epoch `$edate' is in the future"), die
		if $edate > $self->today;
	return $self->{'epoch'} = $edate;
}

sub origin
{
	my $self = shift;
	return $self->{'origin'} if defined $self{'origin'};
	return $self->{'origin'} = $self->make_date('.');
}

##############################################
# Money amount services.

sub currency_code	{ $_[0]->{'currency_code'}; }

sub set_currency_code
{
	my $self = shift;
	confess "bad args" unless @_ == 1;
	return $self->{'currency_code'} = shift;
}

sub make_money
{
	my $self = shift;
	return ABO::Currency->new($_[0], $self->currency_code);
}

##############################################
# Date services.

sub date_language	{ $_[0]->{'date_language'}; }

sub set_date_language
{
	my $self = shift;
	confess "bad args" unless @_ == 1;
	return $self->{'date_language'} = shift;
}

sub make_date
{
	my $self = shift;
	my $dstr = shift;
	my $drel = shift;
	return undef unless defined $dstr;
	my $date = ABO::Date->new($dstr, $self->date_language);
	return $date if defined $date;
	$self->error("invalid date `$dstr'") unless defined $drel;
	if ($dstr =~ m/^[+\-]\d+$/o) {
		$date = $drel + $dstr;
	}
	elsif ($dstr eq 'now') {
		$date = $drel;
	}
	elsif ($dstr eq 'eom') {
		my ($d, $m, $y) = $drel->day_month_year();
		if (++$m > 12) {
			$m = 1;
			$y++;
		}
		$date = ABO::Date->new("1/$m/$y") - 1;
	}
	$self->error("invalid relative date `$dstr'") unless defined $date;
	return $date;
}

1;
