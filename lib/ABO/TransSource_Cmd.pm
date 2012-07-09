package ABO::TransSource_Cmd;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use FileHandle;
use Carp qw(confess);

sub init
{
	my ($self, %args) = @_;
	confess "missing -exec arg" unless defined $args{'-exec'};
	$self->{'cmd'} = $args{'-exec'};
	return $self;
}

sub handle
{
	my $self = shift;
	return 'cmd='.$self->{'cmd'};
}

sub mtime
{
	undef;
}

sub unsorted_transactions
{
	my $self = shift;
	my $cmd = $self->{'cmd'};
	$self->blah("execute command: $cmd");
	my $fh = new FileHandle $cmd.'|' or
		$self->error("cannot fork: $cmd"), return ();
	my $lnum = 0;
	my @trans = ();
	local $x = $self->scope_error_func(sub {
		$self->error("command input, line $lnum: bad transaction: ", @_);
	});
	while (<$fh>)
	{
		chomp;
		$lnum++;
		next if /^\s*#/o or !/\S/o;
		my $t = $self->make(ABO::Transaction, -string => $_);
		push @trans, $t if $t;
	}
	$fh->close;
	return @trans;
}
1;
