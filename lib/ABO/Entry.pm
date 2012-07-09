package ABO::Entry;
use feature 'unicode_strings';

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use overload
	'""' => "as_string",
	'bool' => sub { 1; },
	;

use Carp qw(confess);

my $unique_id_counter = 1;

my %dbcr = (db => 0, cr => 1);
my @dbcr = ('db', 'cr');

sub dbcr_invert
{
	$dbcr[1 ^ $dbcr{$_[0]}];
}

sub init
{
	my ($self, %a) = @_;
	my $date;
	$self->{'unique_id'} = $unique_id_counter++;

	confess "bad -transaction arg" unless UNIVERSAL::isa($a{'-transaction'}, ABO::Transaction);
	$self->{'transaction'} = $a{'-transaction'};

	if (defined $a{'-serialized'})
	{
		my @m = split /\002/, $a{'-serialized'}, 4;
		if (@m != 4)
		{
			$self->error("invalid ".__PACKAGE__." serialization");
			return undef;
		}
		@{$self}{'dbcr', 'account', 'amount', 'detail'} = @m;
	}
	elsif (defined $a{'-string'})
	{
		my @m = split /:/, $a{'-string'}, 4;
		if (@m < 3)
		{
			$self->error("invalid ".__PACKAGE__." string");
			return undef;
		}
		my $det;
		(@{$self}{'dbcr', 'account', 'amount'}, $det) = @m;
		$det = '' unless defined $det;
		$det =~ tr/:/ /;
		$det =~ s/^\s+//o;
		$det =~ s/\s+$//o;
		$self->{'detail'} = $det;
	}
	elsif (defined $a{'-entry'})
	{
		my $e = $a{'-entry'};
		confess "bad -entry arg" unless UNIVERSAL::isa($e, ABO::Entry);
		@{$self}{'dbcr', 'account', 'amount', 'detail'} =
			($e->dbcr, $e->account, $e->amount, $e->detail);
	}
	else
	{
		confess "undefined -dbcr arg" unless defined $a{'-dbcr'};
		confess "undefined -account arg" unless defined $a{'-account'};
		confess "undefined -amount arg" unless defined $a{'-amount'};
		confess "undefined -detail arg" unless defined $a{'-detail'};
		@{$self}{'dbcr', 'account', 'amount', 'detail'} =
			@a{'-dbcr', '-account', '-amount', '-detail'};
	}

	if (!exists $dbcr{$self->{'dbcr'}})
	{
		$self->error("bad dbcr value: ", $self->{'dbcr'});
		return undef;
	}

	if (!UNIVERSAL::isa($self->{'account'}, ABO::Account))
	{
		my $ac = $self->_nucleus->account_list->get_account_byname($self->{'account'})
			or $self->error("invalid account `".$self->{'account'}."'"),
			return undef;
		$self->{'account'} = $ac;
	}

	my $amt = $self->make_money($self->{'amount'});
	if ($amt == 0)
	{
		$self->error("zero amount: $amt");
		return undef;
	}
	elsif ($amt < 0)
	{
		$self->error("negative amount: $amt");
		return undef;
	}
	$self->{'amount'} = $amt;

	return $self;
}

sub unique_id { $_[0]->{'unique_id'} }
sub transaction { $_[0]->{'transaction'} }
sub date { $_[0]->transaction->date }
sub dbcr { $_[0]->{'dbcr'} }
sub account { $_[0]->{'account'} }
sub amount { $_[0]->{'amount'} }
sub who { $_[0]->transaction->who }
sub what { $_[0]->transaction->what }
sub detail { $_[0]->{'detail'} }
sub desc { join ', ', grep { length } ($_[0]->transaction->desc, $_[0]->detail) }

sub cdate
{
	my $self = shift;
	return $self->account->due_date($self);
}

sub serialize
{
	my $self = shift;
	return join "\002",
		$self->dbcr,
		$self->account,
		$self->amount,
		$self->detail;
}

sub as_string
{
	my $self = shift;
	local $^W = undef;
	my $det = $self->detail;
	$det =~ tr/ /:/;
	return	$self->dbcr.':'.$self->account.':'.$self->amount.
		(length $det ? ':'.$det : '');
}

1;
