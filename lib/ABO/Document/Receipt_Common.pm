package ABO::Document::Receipt_Common;

use ABO::Transaction;
use ABO::Utils qw(empty);
use Carp qw(confess);

sub init
{
	my $self = shift;
	$self->_parse_receipt(@_) or return undef;
	$self->_make_receipt_transactions or return undef;
	return $self;
}

sub doctype { 'receipt' }
sub ref { shift->{'ref'} }

sub _make_receipt_transactions
{
	my $self = shift;
	my $t = $self->make(ABO::Transaction,
			-date => $self->{'date'},
			-who => $self->{'customer'},
			-what => ucfirst $self->doctype.' '.$self->ref,
			-entries => [ {
					dbcr => 'db',
					account => $self->{'deposit'},
					amount => $self->{'total'},
					detail => '',
				}, {
					dbcr => 'cr',
					account => $self->{'account'},
					amount => $self->{'total'},
					detail => '',
				} ],
		) or return undef;
	push @{$self->{'transactions'}}, $t;
	return $self;
}

1;
