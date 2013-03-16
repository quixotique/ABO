package ABO::TransSource;
use feature 'unicode_strings';

use Carp qw(confess);

# This package defines a standard "interface" (in Java terminology) to
# any object that can function as a "transaction source", or, in other
# words, is an indivisible source of transactions.

# Return a unique handle for this object.
#
sub handle
{
	confess "must override";
}

# Return the last-modified time of this object, or undef if this is a
# "virtual" object that has no modification time.
#
sub mtime
{
	confess "must override";
}

# Return list of transactions.
#
sub unsorted_transactions
{
	confess "must override";
}

# Return sorted list of transactions.
#
sub transactions
{
	my $self = shift;
	return scalar $self->unsorted_transactions(@_) unless wantarray;
	my @t = $self->unsorted_transactions(@_);
	$self->blah("sort ".scalar(@t)." transactions ".ref($self))
		if @t > 1;
	return sort {
                   $a->date <=> $b->date
                || $a->who cmp $b->who
                || $a->what cmp $b->what
                || $b->amount <=> $a->amount
            } @t;
}

1;
