package ABO::FilterBringForward;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

# Transform a set of transactions such that all entries occurring in
# asset/liability accounts on or before a given date are converted into
# a summary consisting of one (or more) "brought forward" transactions,
# all dated on the given date.  Normally only one "brought forward"
# transaction is generated per account, unless any of the amounts
# brought forward have a "due" date, in which case there is one "brought
# forward" entry created for each distinct due date.  This means that
# the generated "brought forward" entries can have due dates that
# precede their entry dates.  Profit/loss accounts do not get "brought
# forward" entries, of course.

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
	return 'filter.bringforward='.$self->_date.','.$self->_ts->handle;
}

sub mtime
{
	my $self = shift;
	return $self->_ts->mtime;
}

sub unsorted_transactions
{
	my $self = shift;
	shift; # discard 'from' argument

	$self->blah("bring forward to ", $self->_date);

	my $acprofit = defined($_ = $self->_config->var('profit'))
		&& $self->_nucleus->account_list->get_account_byname($_)
		or return ();

	my %acc = ();
	my @trans = $self->_ts->transactions($self->_date + 1, @_);
	my @bf = ();
	while (@trans)
	{
		last if $trans[0]->date > $self->_date;
		my $t = shift @trans;
		for my $e ($t->entries)
		{
			my $ac = $e->account;
			my $due = $e->cdate;
			if ($ac ne $acprofit && $ac->is_asset)
			{
				$acc{$ac} = ['',[]] if !defined $acc{$ac};
				my $amt = $e->amount->clone;
				my $aq = $acc{$ac}->[1];
				if ($acc{$ac}->[0] ne $e->dbcr)
				{
					while (@$aq)
					{
						if ($aq->[0]->{amt} > $amt)
						{
							$aq->[0]->{amt} -= $amt;
							$amt = $self->make_money(0);
							last;
						}
						$amt -= shift(@$aq)->{amt};
					}
				}
				if ($amt)
				{
					confess "oops" if @$aq && $e->dbcr ne $acc{$ac}->[0];
					my $i = @$aq;
					while (--$i >= 0 && $due < $aq->[$i]->{due})
						{}
					if ($i >= 0 && $aq->[$i]->{due} == $due)
					{
						$aq->[$i]->{amt} += $amt;
						$aq->[$i]->{multi} ||= $due != $e->date;
					}
					else
					{
						splice @$aq, $i + 1, 0, {
								amt => $amt,
								due => $due,
								multi => $due != $e->date,
							};
						$acc{$ac}->[0] = $e->dbcr;
					}
				}
			}
		}

	}

	my %bf = ();
	for my $acn (keys %acc)
	{
		my ($ty, $aq) = @{$acc{$acn}};
		next unless @$aq;
		confess "oops" if !length $ty;
		my $ac = $self->_nucleus->account_list->get_account_byname($acn);
		my $amt = $self->make_money(0);
		my $multi = 0;
		for my $a (@$aq)
		{
			$amt += $a->{amt};
			$multi ||= $a->{multi};
		}
		if ($multi)
		{
			for my $a (@$aq)
			{
				my $t = $self->make(
					ABO::Transaction,
					-date => $self->_date,
					-cdate => $a->{due}, 
					-who => $ac->title,
					-what => 'Brought forward',
					-entries => $self->_bf_entries(
							$acprofit,
							{ $acn, $ty eq 'cr'
								? $a->{amt}
								: -$a->{amt}
							}
						),
				) or return ();
				push @bf, $t;
			}
		}
		else
		{
			$bf{$acn} = $self->make_money(0) unless defined $bf{$acn};
			$bf{$acn} += $ty eq 'cr' ? $amt : -$amt;
		}
	}
	my $bfe = $self->_bf_entries($acprofit, \%bf);
	if (defined $bfe && @$bfe)
	{
		my $t = $self->make(
			ABO::Transaction,
			-date => $self->_date,
			-who => '',
			-what => 'Brought forward',
			-entries => $bfe,
		) or return ();
		push @bf, $t;
	}

	return (@bf, @trans);
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
