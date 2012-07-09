package ABO::FilterCancelForward;

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

# Transform a set of transactions such that all balancing transactions
# occurring in asset/liability accounts on or before a given date are
# removed -- they cancel each other out.  The non-balancing transactions
# in accrual accounts (payables and receivables) are kept, those in
# non-accrual accounts are replaced with a single "brought forward"
# transaction.

sub init
{
	my ($self, %args) = @_;
	confess "missing -source arg" unless defined $args{'-source'};
	confess "missing -date arg" unless defined $args{'-date'};
	my $ts = $args{'-source'};
	confess "not a TransSource" unless UNIVERSAL::isa($ts, ABO::TransSource);
	$self->{'ts'} = $ts;
	$self->{'date'} = $args{'-date'};
	return $self;
}

sub _ts { $_[0]->{'ts'} }
sub _date { $_[0]->{'date'} }

sub handle
{
	my $self = shift;
	return 'filter.cancelforward='.$self->_date.','.$self->_ts->handle;
}

sub mtime
{
	my $self = shift;
	return $self->_ts->mtime;
}

sub transactions
{
	my $self = shift;
	shift; # discard 'from' argument

	$self->blah("cancel forward to ", $self->_date);

	my $acprofit = defined($_ = $self->_config->var('profit'))
		&& $self->_nucleus->account_list->get_account_byname($_)
		or return ();

	# First, for each accruable account (receivable or payable) we
	# cancel all balanced entries, leaving only a list of unbalanced
	# entries, the first of which may be partially cancelled.  For
	# each other asset/liability account, just calculate the balance
	# to bring forward.

	my %acc = ();
	my %bf = ();
	my @trans = $self->_ts->transactions($self->_date, @_);
	my @otrans = ();
	while (@trans && $trans[0]->date <= $self->_date)
	{
		my $t = shift @trans;
		push @otrans, $t;
		for my $e ($t->entries)
		{
			my $ac = $e->account;
			next if $ac eq $acprofit;
			my $acc = $acc{$ac};
			$acc = $acc{$ac} = [$self->make_money(0), []]
				unless defined $acc;
			if ($ac->is_receivable || $ac->is_payable)
			{
				my $en = $acc->[1];
				if (!@$en)
				{
					push @$en, $e;
					$acc->[0] = $e->amount;
				}
				elsif ($en->[0]->dbcr eq $e->dbcr)
				{
					my $due = _entry_due($e);
					my $i;
					for ($i = @$en;
					     $i > 0 && $due < _entry_due($en->[$i - 1]);
					     $i--
					)
						{}
					if ($i == 0 && @$en)
					{
						my $amt = $en->[0]->amount - $acc->[0];
						if ($e->amount > $amt)
						{
							$acc->[0] = $e->amount - $amt;
							unshift @$en, $e;
						}
						else
						{
							$acc->[0] += $e->amount;
						}
					}
					else
					{
						splice @$en, $i, 0, $e;
					}
				}
				else
				{
					my $amt = $e->amount->clone;
					while ($amt && @$en)
					{
						if ($acc->[0] <= $amt)
						{
							$amt -= $acc->[0];
							shift @$en;
							$acc->[0] = $en->[0]->amount if @$en;
						}
						else
						{
							$acc->[0] -= $amt;
							$amt = $self->make_money(0);
						}
					}
					if ($amt)
					{
						confess "oops" if @$en;
						push @$en, $e;
						$acc->[0] = $amt;
					}
				}
			}
			elsif ($ac->is_asset)
			{
				$bf{$ac} = $self->make_money(0) unless defined $bf{$ac};
				$bf{$ac} += $e->dbcr eq 'cr' ? $e->amount : -$e->amount;
			}
		}
	}

	# Second, we spot all the un-cancelled entries and locate all
	# the transactions that contain at least one un-cancelled entry.
	# These are the un-cancelled transactions.

	my %eref = ();
	my %tref = ();
	for my $acn (keys %acc)
	{
		my $en = $acc{$acn}->[1];
		next unless @$en;
		my $rem = $acc{$acn}->[0];
		for my $e (@$en)
		{
			$eref{$e->unique_id} = defined $rem ? $rem : $e->amount;
			undef $rem;
			$tref{$e->transaction->unique_id} = 1;
		}
	}
	my @uctrans = grep { $tref{$_->unique_id} } @otrans;

	# Third, we fabricate a single, new, "brought forward"
	# transaction to take care of all the asset/liability account
	# balances, including the balances in the accruable accounts
	# prior to the un-cancelled transactions.  This new transaction
	# is dated just prior to the first un-cancelled transaction
	# (if any).

	for my $t (@uctrans)
	{
		for my $e ($t->entries)
		{
			my $ac = $e->account;
			my $amt;
			if (!defined $eref{$e->unique_id})
			{
				$amt = $e->amount;
			}
			elsif ($eref{$e->unique_id} < $e->amount)
			{
				$amt = $e->amount - $eref{$e->unique_id};
			}
			if ($amt)
			{
				$bf{$ac} = $self->make_money(0) unless defined $bf{$ac};
				$bf{$ac} += $e->dbcr eq 'cr' ? -$amt : $amt;
			}
		}
	}
	my $bfe = $self->_bf_entries($acprofit, \%bf);
	if (defined $bfe && @$bfe)
	{
		my $nt = $self->make(
				ABO::Transaction,
				-date => @uctrans ? $uctrans[0]->date - 1 : $self->_date,
				-who => '',
				-what => 'Brought forward',
				-entries => $bfe,
			) or return undef;
		unshift @uctrans, $nt;
	}


	return (@uctrans, @trans);
}

sub unsorted_transactions
{
	my $self = shift;
	$self->transactions(@_)
}

sub _entry_due
{
	my $e = shift;
	return $e->can('cdate') ? $e->cdate : $e->date;
}

sub _bf_entries
{
	my ($self, $acprofit, $bf) = @_;
	my $bftot = $self->make_money(0);
	$bftot += $bf->{$_} foreach grep { $acprofit ne $_ } keys %$bf;
	$bf->{$acprofit} = -$bftot if $bftot;
	my @bf = ();
	for my $acn (keys %$bf)
	{
		my $amt = $bf->{$acn};
		if ($amt)
		{
			push @bf, {
				dbcr => $amt < 0 ? 'db' : 'cr',
				account => $acn,
				amount => $amt < 0 ? -$amt : $amt,
				detail => '',
			};
		}
	}
	return \@bf;
}

1;
