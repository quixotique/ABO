package ABO::FilterRemoveAccruedPayables;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

# Transform a set of transactions to remove all liabilities in the form of
# unpaid (outstanding) accounts payable, thereby converting to cash-based
# expenses rather than accrual-based expenses.

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
	return 'filter.remove-accrued-payables='.$self->_ts->handle;
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

	$self->blah("remove accrued payables");

	# First, pull out all transactions that contain credits to payable
	# accounts, and store all those transactions' debits (to other
	# accounts).

	for my $t ($self->_ts->transactions($from, undef, @_))
	{
		my @ents = $t->entries;
		my @cr = grep { $_->dbcr eq 'cr' } @ents;
		my @db = grep { $_->dbcr eq 'db' } @ents;
		my @ncr = ();
		for my $cre (@cr)
		{
			my $crac = $cre->account;
			if ($crac->is_payable)
			{
				my ($rem, @en) = $self->_cut_entries(\@db, $cre->amount);
				confess "oops" if $rem != 0;
				push @{$acc{$crac}}, @en;
			}
			else
			{
				push @ncr, $cre;
			}
		}
		if (@ncr && @ncr < @cr)
		{
			my $nt = $self->make(ABO::Transaction,
				-date => $t->date,
				-cdate => $t->cdate,
				-who => $t->who,
				-what => $t->what,
				-entries => [ @ncr, @db ],
			) or return ();
			push @trans, $nt;
		}
		elsif (@ncr)
		{
			push @trans, $t;
		}
	}

	# Next, sort all the stored debits by due date, then date, then
	# account.  This is to guarantee the same results from the calls to
	# _cut_entries() below, independent of the order in which the
	# transaction entries are presented to us.

	for my $acn (keys %acc)
	{
		@{$acc{$acn}} = sort {
				$a->cdate <=> $b->cdate
				|| $a->date <=> $b->date
				|| $a->account <=> $b->account
			}
			@{$acc{$acn}};
	}

	# Last, replace all debits to payable accounts with stored debits to
	# the same value, in sorted order.  If there are any stored debits left
	# over (unpaid bills), we drop them (that's the whole point of the
	# exercise -- to get rid of accrued expenses).  If we run out of stored
	# debits for an account, then we retain the left-over debit to the
	# payable account, indicating a pre-paid account which, although
	# refundable, should be accounted as a simple expense in cash books.

	for my $t (@trans)
	{
		my @ents = $t->entries;
		my @cr = grep { $_->dbcr eq 'cr' } @ents;
		my @db = grep { $_->dbcr eq 'db' } @ents;
		my @ndb = ();
		my $changed = 0;
		for my $dbe (@db)
		{
			my $dbac = $dbe->account;
			if ($dbac->is_payable)
			{
				my ($rem, @en) = $self->_cut_entries($acc{$dbac}, $dbe->amount);
				if (!@en)
				{
					push @ndb, $dbe;
				}
				else
				{
					push @ndb, @en;
					$changed = 1;
					if ($rem)
					{
						my $ne = $self->make(
							ABO::Entry,
							-transaction => $t,
							-dbcr => $dbe->dbcr,
							-account => $dbac,
							-amount => $rem,
							-detail => $dbe->detail,
						) or return ();
						push @ndb, $ne;
					}
				}
			}
			else
			{
				push @ndb, $dbe;
			}
		}
		if ($changed)
		{
			my $nt = $self->make(ABO::Transaction,
				-date => $t->date,
				-cdate => $t->cdate,
				-who => $t->who,
				-what => $t->what,
				-entries => [ @cr, @ndb ],
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
	while ($amt && $en && @$en)
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
			) or die "A"; #return ();
			unshift @$en, $ne;
			$e = $self->make(
				ABO::Entry,
				-transaction => $e->transaction,
				-dbcr => $e->dbcr,
				-account => $e->account,
				-amount => $amt,
				-detail => $e->detail,
			) or die "B"; #return ();
			$amt = $self->make_money(0);
		}
		push @ret, $e;
	}
	return ($amt, @ret);
}

1;
