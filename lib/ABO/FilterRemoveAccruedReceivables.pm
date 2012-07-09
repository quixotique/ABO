package ABO::FilterRemoveAccruedReceivables;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

# Transform a set of transactions to remove all accounts receivable, converting
# to cash-based income rather than accrual-based income.

sub init
{
	my ($self, %args) = @_;
	confess "missing -source arg" unless defined $args{'-source'};
	my $ts = $args{'-source'};
	confess "not a TransSource" unless UNIVERSAL::isa($ts, ABO::TransSource);
	$self->{'ts'} = $ts;
	return $self;
}

sub _ts { shift->{'ts'} }

sub handle
{
	my $self = shift;
	return 'filter.remove-accrued-receivables='.$self->_ts->handle;
}

sub mtime
{
	my $self = shift;
	return $self->_ts->mtime;
}

sub unsorted_transactions
{
	my $self = shift;
	my $from = shift;
	my $to = shift;

	my %acc = ();
	my @ret = ();
	my @trans = ();

	$self->blah("remove accrued receivables");

	# First, pull out all transactions that contain debits to receivable
	# accounts, and store all those transactions' credits (to other
	# accounts).

	for my $t ($self->_ts->transactions($from, $to, @_))
	{
		my @ents = $t->entries;
		my @cr = grep { $_->dbcr eq 'cr' } @ents;
		my @db = grep { $_->dbcr eq 'db' } @ents;
		my @ndb = ();
		for my $dbe (@db)
		{
			my $dbac = $dbe->account;
			if ($dbac->is_receivable)
			{
				my ($rem, @en) = $self->_cut_entries(\@cr, $dbe->amount);
				confess "oops" if $rem != 0;
				push @{$acc{$dbac}}, @en;
			}
			else
			{
				push @ndb, $dbe;
			}
		}
		if (@ndb && @ndb < @db)
		{
			my $nt = $self->make(ABO::Transaction,
				-date => $t->date,
				-cdate => $t->cdate,
				-who => $t->who,
				-what => $t->what,
				-entries => [ @ndb, @cr ],
			) or return ();
			push @trans, $nt;
		}
		elsif (@ndb)
		{
			push @trans, $t;
		}
	}

	# Next, sort all the stored credits by due date, then date, then
	# account.  This is to guarantee the same results from the calls to
	# _cut_entries() below, independent of the order in which the
	# transaction entries are presented to us.

	for my $acn (keys %acc)
	{
		@{$acc{$acn}} = sort {
				$a->transaction->cdate <=> $b->transaction->cdate
				|| $a->date <=> $b->date
				|| $a->account cmp $b->account
			}
			@{$acc{$acn}};
	}

	# Last, replace all credits to receivable accounts with stored credits
	# to the same value, in sorted order.  If there are any stored credits
	# left over, we drop them (that's the whole point of the exercise -- to
	# get rid of accrued income).  If we run out of stored credits for an
	# account, then we retain the remaining credits to the receivable
	# account, which indicates payment received before an invoice was
	# raised.

	for my $t (@trans)
	{
		my @ents = $t->entries;
		my @cr = grep { $_->dbcr eq 'cr' } @ents;
		my @db = grep { $_->dbcr eq 'db' } @ents;
		my @ncr = ();
		my $changed = 0;
		for my $cre (@cr)
		{
			my $crac = $cre->account;
			if ($crac->is_receivable)
			{
				my ($rem, @en) = $self->_cut_entries($acc{$crac}, $cre->amount);
				if (!@en)
				{
					push @ncr, $cre;
				}
				else
				{
					push @ncr, @en;
					$changed = 1;
					if ($rem)
					{
						my $ne = $self->make(
							ABO::Entry,
							-transaction => $t,
							-dbcr => $cre->dbcr,
							-account => $crac,
							-amount => $rem,
							-detail => $cre->detail,
						) or return ();
						push @ncr, $ne;
					}
				}
			}
			else
			{
				push @ncr, $cre;
			}
		}
		if ($changed)
		{
			my $nt = $self->make(ABO::Transaction,
				-date => $t->date,
				-cdate => $t->cdate,
				-who => $t->who,
				-what => $t->what,
				-entries => [ @db, @ncr ],
			) or return ();
			push @ret, $nt;
		}
		else
		{
			push @ret, $t;
		}
	}

	return @ret;
}

sub _cut_entries
{
	my ($self, $en, $amt) = @_;
	$amt = $self->make_money($amt);
	my @ret = ();
	while ($amt && @$en)
	{
		my $e = shift @$en;
		if ($e->amount <= $amt)
		{
			$amt -= $e->amount;
		}
		else
		{
			my $ne = $self->make(
				ABO::Entry,
				-transaction => $e->transaction,
				-dbcr => $e->dbcr,
				-account => $e->account,
				-amount => $e->amount - $amt,
				-detail => $e->detail,
			) or return ();
			unshift @$en, $ne;
			$e = $self->make(
				ABO::Entry,
				-transaction => $e->transaction,
				-dbcr => $e->dbcr,
				-account => $e->account,
				-amount => $amt,
				-detail => $e->detail,
			) or return ();
			$amt = $self->make_money(0);
		}
		push @ret, $e;
	}
	return ($amt, @ret);
}

1;
