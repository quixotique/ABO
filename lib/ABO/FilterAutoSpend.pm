package ABO::FilterAutoSpend;

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

# Transform a set of transactions such that the balance of a nominated asset
# account is kept below a certain "float level" by synthesising transactions to
# credit the asset account and debit another nominated account (typically a
# profit/loss account, but it doesn't have to be).  This was originally
# intended to generate the expenses from a cash in hand account.

sub init
{
	my ($self, %args) = @_;
	confess "missing -source arg" unless defined $args{'-source'};
	confess "missing -account arg" unless defined $args{'-account'};
	confess "missing -debit arg" unless defined $args{'-debit'};
	confess "missing -float arg" unless defined $args{'-float'};
	my $ts = $args{'-source'};
	my $ac = $args{'-account'};
	my $db = $args{'-debit'};
	my $fl = $args{'-float'};
	my $who = $args{'-who'};
	my $what = $args{'-what'};
	my $from = $args{'-from'};
	my $to = $args{'-to'};
	confess "not a TransSource" unless UNIVERSAL::isa($ts, ABO::TransSource);
	if (!UNIVERSAL::isa($ac, ABO::Account))
	{
		$ac = $self->_nucleus->account_list->get_account_byname($ac)
			or $self->error("no such account `$ac'"), return ();
	}
	$self->error("`$ac' is not an asset account"), return () unless $ac->is_asset;
	if (!UNIVERSAL::isa($db, ABO::Account))
	{
		my $n = $db;
		$db = $self->_nucleus->account_list->get_account_byname($db)
			or $self->error("no such account `$n'"), return ();
	}
	$fl = $self->make_money($fl) unless UNIVERSAL::isa($fl, ABO::Currency);
	$self->error("negative float amount"), return () if $fl < 0;
	$who = '' unless defined $who;
	$what = '' unless defined $what;
	if (defined $from) {
		$from = $self->make_date($from) or confess "bad -from arg";
	}
	if (defined $to) {
		$to = $self->make_date($to) or confess "bad -to arg";
	}
	$self->{'ts'} = $ts;
	$self->{'account'} = $ac;
	$self->{'debit'} = $db;
	$self->{'float'} = $fl;
	$self->{'who'} = $who;
	$self->{'what'} = $what;
	$self->{'from'} = $from;
	$self->{'to'} = $to;
	return $self;
}

sub _ts { $_[0]->{'ts'} }
sub _account { $_[0]->{'account'} }
sub _debit { $_[0]->{'debit'} }
sub _float { $_[0]->{'float'} }
sub _who { $_[0]->{'who'} }
sub _what { $_[0]->{'what'} }
sub _from { $_[0]->{'from'} }
sub _to { $_[0]->{'to'} }

sub handle
{
	my $self = shift;
	return 'filter.autospend='.$self->_account.','.$self->_debit.','.$self->_float.','.($self->_from || '').','.($self->_to || '').','.$self->_ts->handle;
}

sub mtime
{
	my $self = shift;
	return $self->_ts->mtime;
}

sub transactions
{
	my $self = shift;

	$self->blah("auto spend account ", $self->_account,
		", debit account ", $self->_debit,
		", keep float of ", $self->_float,
		defined $self->_from ? (", from ".$self->_from) : (),
		defined $self->_to ? (", to ".$self->_to) : ()
	);

	my $date;
	my @trans = $self->_ts->transactions(@_);
	my @otrans = ();
	my $bal = $self->make_money(0);
	while (@trans)
	{
		my $t = shift @trans;
		if (defined $date && $t->date != $date &&
		    !($self->_from && $date < $self->_from) &&
		    !($self->_to && $date > $self->_to))
		    
		{
			$self->_spend_trans(\@otrans, \$bal, $date) or return ();
		}
		push @otrans, $t;
		$date = $t->date;
		for my $e ($t->entries)
		{
			my $ac = $e->account;
			if ($ac eq $self->_account)
			{
				my $amt = $e->amount;
				if ($e->dbcr eq 'db')
				{
					$bal -= $amt;
				}
				else
				{
					$bal += $amt;
				}
			}
		}
	}
	if (defined $date &&
	    !($self->_from && $date < $self->_from) &&
	    !($self->_to && $date > $self->_to))
	{
		$self->_spend_trans(\@otrans, \$bal, $date) or return ();
	}

	return @otrans;
}

sub unsorted_transactions
{
	my $self = shift;
	$self->transactions(@_)
}

sub _spend_trans
{
	my ($self, $tl, $rbal, $date) = @_;
	if ($$rbal < -$self->_float)
	{
		my $spend = -$$rbal - $self->_float;
		my $nt = $self->make(
			ABO::Transaction,
			-date => $date,
			-who => $self->_who,
			-what => $self->_what,
			-entries => [
				{
					dbcr => 'cr',
					account => $self->_account,
					amount => $spend,
					detail => '',
				},
				{
					dbcr => 'db',
					account => $self->_debit,
					amount => $spend,
					detail => '',
				},
			],
		) or return 0;
		$$rbal += $spend;
		push @$tl, $nt;
	}
	return 1;
}

1;
