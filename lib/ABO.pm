package ABO;

use feature 'unicode_strings';

require ABO::Base;
@ISA = qw(ABO::Base);

use Carp qw(confess);
use Cwd ();

sub new
{
	my $class = shift;
	my $self = bless {}, ref($class) || $class;
	return $self->init(@_);
}

sub init
{
	my ($self, %args) = @_;

	# Start the ABO Nucleus.
	$self->_set_nucleus(ABO::Nucleus->new) or return undef;
	$self->_nucleus->set_error_reporter(
		$self->make(ABO::Error,
			$args{-error} || sub { warn("ABO: ", @_, "\n") }
		)
	) or return undef;
	my $config = $self->make(ABO::Config, $args{-pwd} || Cwd::cwd)
		or return undef;
	$self->_nucleus->set_config($config) or return undef;

	# Set up run-time options.
	$self->_nucleus->set_option('regenerate-cache', $args{-regenerate_cache});
	$self->_nucleus->set_option('remove-accrued-receivables', $args{-remove_accrued_receivables} || $args{-cash});
	#$self->_nucleus->set_option('remove-accrued-payables', $args{-remove_accrued_payables} || $args{-cash});
	$self->_nucleus->set_option('verbose', $args{-verbose});

	# Set the default currency.
	$self->_nucleus->set_currency_code($self->_config->var('currency'));

	# Set the default date language.
	$ABO::Date::default_lang = 'en';
	$self->_nucleus->set_date_language($self->_config->var('date_language'));

	# Set up the account list.
	my $aclist = $self->make(ABO::AccountList) or return undef;
	$self->_nucleus->set_account_list($aclist);

	# Read the optional filter list.
	my $filist = $self->make(ABO::FilterList);

	# Set up all sources of transactions.
	my @ts = ();
	my $ts;
	if (defined $args{-source})
	{
		$ts = $self->make(ABO::TransSource_File,
				-file => $args{-source}
			)
			or return undef;
	}
	elsif (defined ($_ = $self->_config->varx('transaction_src')))
	{
		if (/^!/o)
		{
			$ts = $self->make(ABO::TransSource_Cmd, -exec => substr($_, 1));
		}
		else
		{
			$ts = $self->make(ABO::TransSource_File, -file => $_);
		}
	}
	else
	{
		my $curbook = $self->_config->var('current_book') or return undef;
		$ts = $self->make(ABO::Book, -name => $curbook) or return undef;
		$self->{'current_book'} = $ts;
		$self->{'docbase'} = $ts->docbase;
	}

	# Instantiate the filters on the filter list.
	$ts = $filist->filter($ts) if $filist;
	return undef unless $ts;

	$self->{'tsource'} = $ts;

	return $self;
}

sub _tsource
{
	my ($self, $from, $to) = @_;

	my $ts = $self->{'tsource'};
	if ($self->_nucleus->option('remove-accrued-receivables'))
	{
		$ts = $self->make(ABO::FilterRemoveAccruedReceivables, -source => $ts)
			or return undef;
	}
	if ($self->_nucleus->option('remove-accrued-payables'))
	{
		$ts = $self->make(ABO::FilterRemoveAccruedPayables, -source => $ts)
			or return undef;
	}
	if ($from)
	{
		if ($to && $from > $to + 1)
		{
			$self->error("from-date `$from' is later than to-date `$to'");
			return undef;
		}
		$ts = $self->make(
				ABO::FilterBringForward,
				-source => $ts,
				-date => $from - 1,
			)
			or return undef
			if $from ne '.';
	}
	return $ts;
}


sub today	 { shift->_nucleus->today; }
sub vars	 { shift->_config->vars(@_); }
sub var		 { shift->_config->var(@_); }
sub account_list { shift->_nucleus->account_list; }
sub current_book { shift->{'current_book'}; }
sub docbase	 { shift->{'docbase'}; }

sub default_from
{
	my $self = shift;
	$self->current_book ? $self->current_book->open_date : $self->_nucleus->origin;
}

sub parse_from_date
{
	my ($self, $arg) = @_;
	confess "bad arg" unless defined $arg;
	local $x = $self->scope_error_prefix("bad `from' value: ");
	return $self->_nucleus->origin if $arg eq 'start';
	return $self->default_from if $arg eq '' || $arg eq 'default';
	return $self->make_date($arg);
}

sub parse_to_date
{
	my ($self, $arg) = @_;
	confess "bad arg" unless defined $arg;
	local $x = $self->scope_error_prefix("bad `to' value: ");
	return $self->_nucleus->today if $arg eq '' || $arg eq 'now';
	return $self->make_date($arg);
}

sub unsorted_transactions
{
	my $self = shift;
	my ($from, $to) = @_;
	my $ts = $self->_tsource(@_) or return ();
	grep { !$to || $_->date <= $to } $ts->unsorted_transactions(@_);
}

sub transactions
{
	my $self = shift;
	my ($from, $to) = @_;
	my $ts = $self->_tsource(@_) or return ();
	grep { !$to || $_->date <= $to } $ts->transactions(@_);
}

sub get_period_summary
{
	my $self = shift;
	my ($from, $to) = @_;
	my %summ = ();
	for my $ac ($self->account_list->accounts)
	{
		$summ{$ac->name} = {
				bf => $self->make_money(0),
				db => $self->make_money(0),
				cr => $self->make_money(0),
				c_bf => $self->make_money(0),
				c_db => $self->make_money(0),
				c_cr => $self->make_money(0),
			};
	}

	for my $t ($self->unsorted_transactions($from))
	{
		my $broughtforward = $from && $t->date < $from;
		for my $e ($t->entries)
		{
			my $dbcr = $e->dbcr;
			my $ac = $e->account;
			my $amt = $e->amount;
			if (!$to || $t->date <= $to)
			{
				if ($broughtforward)
				{
					if ($ac->is_asset && $dbcr eq 'db')
					{
						$summ{$ac->name}->{bf} -= $amt
					}
					elsif ($ac->is_asset && $dbcr eq 'cr')
					{
						$summ{$ac->name}->{bf} += $amt
					}
				}
				else
				{
					$summ{$ac->name}->{$dbcr} += $amt;
				}
			}
			if (!$to || $e->cdate <= $to)
			{
				if ($broughtforward)
				{
					if ($ac->is_asset && $dbcr eq 'db')
					{
						$summ{$ac->name}->{c_bf} -= $amt
					}
					elsif ($ac->is_asset && $dbcr eq 'cr')
					{
						$summ{$ac->name}->{c_bf} += $amt
					}
				}
				else
				{
					$summ{$ac->name}->{"c_$dbcr"} += $amt;
				}
			}
		}
	}
	return \%summ;
}

sub get_period_flow
{
	my $self = shift;
	my ($from, $to, $crit) = @_;
	my %flow = (
		'' => {
			bf => $self->make_money(0),
			c_bf => $self->make_money(0),
		}
	);
	for my $ac ($self->account_list->accounts)
	{
		next if &$crit($ac);
		$flow{$ac->name} = {
				db => $self->make_money(0),
				cr => $self->make_money(0),
				c_db => $self->make_money(0),
				c_cr => $self->make_money(0),
			};
	}

	for my $t ($self->unsorted_transactions($from))
	{
		my $broughtforward = $from && $t->date < $from;
		if ($broughtforward) {
			for my $e ($t->entries)
			{
				my $ac = $e->account;
				next unless &$crit($ac);
				my $dbcr = $e->dbcr;
				my $amt = $e->amount;
				if (!$to || $t->date <= $to)
				{
					$flow{''}->{bf} += $dbcr eq 'cr' ? $amt : -$amt;
				}
				if (!$to || $e->cdate <= $to)
				{
					$flow{''}->{c_bf} += $dbcr eq 'cr' ? $amt : -$amt;
				}
			}
			next;
		}
		my $dbtot = $self->make_money(0);
		my $crtot = $self->make_money(0);
		my $ftot = $self->make_money(0);
		for my $e ($t->entries)
		{
			my $amt = $e->amount;
			my $crit_p = &$crit($e->account);
			if ($e->dbcr eq 'cr')
			{
				if ($crit_p) {
					$ftot += $amt
				}
				else {
					$crtot += $amt;
				}
			}
			else
			{
				if ($crit_p) {
					$ftot -= $amt;
				}
				else {
					$dbtot += $amt;
				}
			}
		}
		my $ratio = 1;
		my $dbcr;
		if ($ftot > 0)
		{
			$dbcr = 'db';
			$ratio = $ftot / ($ftot + $crtot) if $crtot != 0;
		}
		elsif ($ftot < 0)
		{
			$dbcr = 'cr';
			$ratio = $ftot / ($ftot - $dbtot) if $dbtot != 0;
		}
		if ($dbcr)
		{
			for my $e ($t->entries)
			{
				my $ac = $e->account;
				next if &$crit($ac) || $e->dbcr ne $dbcr;
				my $amt = $e->amount * $ratio;
				if (!$to || $t->date <= $to)
				{
					$flow{$ac->name}->{"$dbcr"} += $amt;
				}
				if (!$to || $e->cdate <= $to)
				{
					$flow{$ac->name}->{"c_$dbcr"} += $amt;
				}
			}
		}
	}
	return \%flow;
}

sub colwid_signed
{
	my $self = shift;
	my $pos = $self->make_money($self->var('cope'));
	my $neg = -$pos;
	my ($lp, $ln) = (length("$pos"), length("$neg"));
	return $lp > $ln ? $lp : $ln;
}

sub colwid_unsigned
{
	my $self = shift;
	my $pos = $self->make_money($self->var('cope'));
	$pos = -$pos if $pos < 0;
	return length("$pos");
}

1;
