package ABO::TransSource_File;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use FileHandle;

sub init
{
	my $self = shift;
	my $file = shift;
	my $fh = new FileHandle "<$file" or
		$self->error("cannot open `$file' - $!"), return undef;
	$self->{'file'} = $file;
	$self->{'fh'} = $fh;
	return $self;
}

sub handle
{
	my $self = shift;
	return 'file='.$self->{'file'};
}

sub mtime
{
	my $self = shift;
	my $file = $self->{'file'};
	my @s = stat $file or
		$self->error("cannot stat `$file' - $!"), return undef;
	return $s[9];
}

sub unsorted_transactions
{
	my $self = shift;
	my $file;
	my $fh;
	$file = $self->{'file'};
	$fh = $self->{'fh'};
	seek $fh, 0, 0 or
		$self->error("cannot rewind `$file' - $!"), return ();
	my $lnum = 0;
	my @trans = ();
	local $x = $self->scope_error_func(sub {
		$self->error("\"$file\" line $lnum: bad transaction: ", @_);
	});
	while (<$fh>)
	{
		chomp;
		$lnum++;
		next if /^\s*#/o or !/\S/o;
		my $t = $self->make(ABO::Transaction, -string => $_);
		push @trans, $t if $t;
	}
	return @trans;
}

1;
