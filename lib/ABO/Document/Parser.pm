package ABO::Document::Parser;
use feature 'unicode_strings';

# This class is solely intended to be sub-classed by the various
# document parser classes.

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);

sub init
{
	my $self = shift;
	$self->{'attributes'} = [];
	$self->{'attribute'} = {};
	$self->{'transactions'} = [];
	return $self->_parse(@_);
}

sub unsorted_transactions { @{shift()->{'transactions'}} }
sub attributes { @{shift()->{'attributes'}} }

sub attribute
{
	my $self = shift;
	confess "bad args" unless @_ && defined $_[0];
	my $att = shift;
	my $val = $self->{'attribute'}->{$att};
	$self->error("no such attribute `$att'") unless defined $val;
	return $val;
}

sub doctype { confess "must override"; }
sub ref { confess "must override"; }
sub probe { confess "must override"; }

# Private methods.

sub _parse { confess "must override"; }

sub _set_attribute
{
	my ($self, $att, $val) = @_;
	my $rval = \$self->{'attribute'}->{$att};
	push @{$self->{'attributes'}}, $att unless defined $$rval;
	$$rval = $val;
	return $self;
}

1;
