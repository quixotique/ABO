package ABO::TransBase_Concat;

use ABO::Base;
use ABO::TransBase;
@ISA = qw(
	ABO::Base
	ABO::TransBase
);

use Carp qw(confess);

sub init
{
	my ($self, %args) = @_;
	confess "missing -name arg" unless defined $args{'-name'};
	confess "missing -sources arg" unless defined $args{'-sources'};
	confess "-sources arg not array ref" unless ref $args{'-sources'} eq 'ARRAY';
	$self->{'name'} = $args{'-name'};
	$self->{'concat'} = $args{'-concat'};
	my $cats = $self->{'cats'} = [];
	my $cat = $self->{'cat'} = {};
	for my $ts (@{$args{'-sources'}})
	{
		confess "bad transaction source"
			if !UNIVERSAL::isa($ts, ABO::TransSource);
		push @$cats, $ts->handle;
		$cat->{$ts->handle} = $ts;
	}
	return $self;
}

sub handle
{
	return 'catbase='.$_[0]->{'name'};
}

sub mtime
{
	my $self = shift;
	my $mtime;
	for $ts (values %{$self->{'cat'}})
	{
		my $tsmtime = $ts->mtime;
		return undef unless defined $tsmtime;
		$mtime = $tsmtime unless defined($mtime) && $mtime >= $tsmtime;
	}
	return $mtime;
}

sub get_handles
{
	return @{$_[0]->{'cats'}};
}

sub fetch
{
	return $_[0]->{'cat'}->{$_[1]};
}

sub transactions
{
	my $self = shift;
	return $self->SUPER::transactions(@_) unless $self->{'concat'};
	my @trans = ();
	my $last;
	for my $h ($self->get_handles)
	{
		my $p = $self->fetch($h) or return ();
		my @t = $p->transactions(@_) or return ();
		confess "sources overlap" if defined $last && $last > $t[0]->date;
		push @trans, @t;
		$last = $t[$#t]->date;

	}
	return @trans;
}

1;
