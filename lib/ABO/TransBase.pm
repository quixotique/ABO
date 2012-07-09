package ABO::TransBase;

use ABO::TransSource;
@ISA = qw(
	ABO::TransSource
);

use Carp qw(confess);

# This package defines a standard "interface" (in Java terminology) to
# any object that can function as a "transaction base", or, in other
# words, is a source of transactions that is divided into identifiable
# parts, where each part is individually cacheable if so desired.
#
# This interface extends the "TransSource" interface, so that a
# TransBase can also be used as an indivisible source of sorted
# transactions if desired.  This is done in the generic implementation
# of the "unsorted_transactions" method below.

# Return a unique handle for this object.
sub handle
{
	my ($self) = @_;
	confess "must override";
}

# Return a list of handles to all parts.
sub get_handles
{
	my ($self) = @_;
	confess "must override";
}

# Fetch a part given its handle.
sub fetch
{
	my ($self, $dh) = @_;
	confess "must override";
}

# Return the aggregate list of transaction from all parts.
sub unsorted_transactions
{
	my $self = shift;
	my @trans = ();
	for my $h ($self->get_handles)
	{
#local $p = (defined($p) ? $p.'\\' : '').$h;
#print STDERR "$p\n";
		my $p = $self->fetch($h) or return ();
		my @t = $p->unsorted_transactions(@_) or return ();
		push @trans, @t;
	}
	return @trans;
}

1;
