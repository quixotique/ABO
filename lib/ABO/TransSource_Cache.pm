package ABO::TransSource_Cache;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Carp qw(confess);
use FileHandle;

sub init
{
	my ($self, %args) = @_;
	confess "missing -file arg" unless defined $args{'-file'};
	my $file = $args{'-file'};
	my $ts = $args{'-source'};
	confess "not a TransSource" if defined $ts && !UNIVERSAL::isa($ts, ABO::TransSource);
	unlink $file if $ts && $self->_nucleus->option('regenerate-cache');
	$self->{'file'} = $file;
	$self->{'ts'} = $ts;
	return $self;
}

sub _ts { shift->{'ts'} }
sub _file { shift->{'file'} }

sub _error
{
	my $self = shift;
	my $file = $self->_file;
	$self->error("cache \"$file\": ", @_);
}

################################################
# Implementation of "TransBase" interface.

sub handle
{
	return 'cache='.$_[0]->_file;
}

sub mtime
{
	my $self = shift;
	return $self->_ts ? $self->_ts->mtime : $self->_mtime;
}

sub unsorted_transactions
{
	my $self = shift;
	return $self->transactions(@_);
}

sub transactions
{
	my $self = shift;
	my $file = $self->_file;
	if ($self->_ts && !defined $self->_ts->mtime)
	{
		# Don't cache virtual transaction sources.
		unlink $file;
		return $self->_ts->transactions(@_);
	}
	my $mtime = $self->_mtime;
	if (defined $mtime && (!$self->_ts || $mtime >= $self->_ts->mtime))
	{
		my @t = $self->_read;
		if (@t)
		{
			$self->blah("fetch transactions from cache `$file'");
			return @t;
		}
	}
	return $self->_write;
}

sub _mtime
{
	my $self = shift;
	my @s = stat $self->_file or return undef;
	return $s[9];
}

sub _read
{
	my $self = shift;
	my $file = $self->_file;
	my $fh = new FileHandle "<$file" or return ();
	my $lnum = 0;
	my @trans = ();
	local $x = $self->scope_error_func(sub {
		$self->_error("corrupt data, line $lnum: ", @_);
	});
	while (<$fh>)
	{
		chomp;
		$lnum++;
		my $t = $self->make(ABO::Transaction, -serialized => $_) or
			$fh->close, return ();
		push @trans, $t;
	}
	$fh->close;
	return @trans;
}

sub _write
{
	my $self = shift;
	my $file = $self->_file;
	$self->_error("cannot regenerate file - missing transaction source"),
		return ()
		if !$self->_ts;
	my @trans = $self->_ts->transactions or return ();
	unlink $file;
	my $fh = new FileHandle ">$file" or
		$self->_error("cannot create file - $!"),
		return ();
	$self->blah("write cache `$file'");
	$fh->print($_->serialize, "\n") foreach @trans;
	$fh->close;
	return @trans;
}

1;
