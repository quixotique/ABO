package ABO::Account;

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use overload
	'""' => "as_string",
	'bool' => sub { 1; },
	'eq' => "equals",
	'==' => "equals",
	'ne' => "notequals",
	'!=' => "notequals",
	'cmp' => "compare",
	;

sub init
{
	my $self = shift;
	local $_ = shift;
	if (/^(\w+)(\s+(\S.*))?$/o)
	{
		$self->{'name'} = $1;
		$self->{'details'} = $3;
	}
	else
	{
		$self->error("invalid account text `$_'");
		return undef;
	}
	$self->{'is_gst_credit'} = $self->{'name'} eq $self->_config->var('invoice_gst_credit');
	$self->{'is_gst_debit'} = $self->{'name'} eq $self->_config->var('bill_gst_debit');
	return $self;
}

sub as_string
{
	$_[0]->name;
}

sub equals
{
	my ($self, $a) = @_;
	$self->name eq (ref($a) eq ref($self) ? $a->name : "$a");
}

sub notequals
{
	my ($self, $a) = @_;
	$self->name ne (ref($a) eq ref($self) ? $a->name : "$a");
}

sub compare
{
	my ($self, $n, $rev) = @_;
	my $r = $self->name cmp (ref($n) eq ref($self) ? $n->name : "$n");
	return $rev ? -$r : $r;
}

sub name
{
	$_[0]->{'name'};
}

sub title
{
	my $self = shift;
	local $_ = $self->{'details'};
	return /"([^"]+)"/o ? $1 : "[".$self->{'name'}."]";
}

sub _type
{
	my $self = shift;
	local $_ = $self->{'details'};
	return 'AssetLiability' if /^(ass|lia|pay|rec)/io;
	return 'ProfitLoss';
}

sub is_asset
{
	return $_[0]->_type eq 'AssetLiability';
}

sub is_liability
{
	my $self = shift;
	local $_ = $self->{'details'};
	return /^lia/io ? 1 : 0;
}

sub category
{
	my $self = shift;
	local $_ = $self->{'details'};
	return $1 if /^\w*:(\w+)/o;
	return $1 if /^(pay|rec)/o;
	return 'profit';
}

sub is_profit
{
	return $_[0]->_type eq 'ProfitLoss';
}

sub is_payable
{
	my $self = shift;
	return $self->{'details'} =~ /^pay/o;
}

sub is_receivable
{
	my $self = shift;
	return $self->{'details'} =~ /^rec/o;
}

sub is_accrue
{
	my $self = shift;
	return $self->is_payable || $self->is_receivable;
}

sub due_date
{
	my $self = shift;
	my $e = shift;
	if (($self->{'is_gst_credit'} && $e->dbcr eq 'cr') ||
	    ($self->{'is_gst_debit'} && $e->dbcr eq 'db')
	){
		my $d = $e->date;
		my $m = (4, 4, 4, 7, 7, 7, 10, 10, 10, 1, 1, 1)[$d->month - 1];
		return $self->make_date([1, $m, $d->year])
	}
	return $e->transaction->cdate;
}

1;
