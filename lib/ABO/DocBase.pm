package ABO::DocBase;

use ABO::Base;
use ABO::TransBase;
@ISA = qw(
	ABO::Base
	ABO::TransBase
);

use ABO::Utils qw(max);

use Carp qw(confess);

my %doctypes = (
	invoice => 1,
	receipt => 1,
	journal => 1,
);

sub init
{
	my ($self, %args) = @_;
	confess "missing -dir arg" unless defined $args{'-dir'};
	$self->{'dir'} = $args{'-dir'};
	$self->{'docdirs'} = {};
	my $err = 0;
	for my $doctype (keys %doctypes)
	{
		my $dir = $self->_config->var($doctype.'_dir') or
			$err = 1, next;
		$self->error("$doctype directory `$dir' does not exist"),
			$err = 1 unless -d $dir;
		$self->{'docdirs'}->{$doctype} = $dir;
	}
	return undef if $err;
	return $self;
}

##############################################################################
# Implementation of "TransBase" interface.

sub handle
{
	'docbase='.shift()->{'dir'};
}

sub get_handles
{
	my $self = shift;
	return map { $self->handles($_) } keys %doctypes;
}

sub mtime
{
	my $self = shift;
	my $mtime;
	for my $doctype (keys %doctypes)
	{
		for my $file (
			$self->doctype_dir($doctype),
			$self->_all_files($doctype)
		)
		{
			my @s = stat $file or return undef;
			my $fmtime = max($s[9], $s[10]);
			next if defined($mtime) && $mtime > $fmtime;
			$mtime = $fmtime;
		}
	}
	return $mtime;
}

sub fetch
{
	shift->get_document(@_);
}

##############################################################################
# DocBase methods.

sub allocref
{
	my $self = shift;
	my $doctype = shift;
	my $dh = $self->_alloc_handle($doctype) or return undef;
	return $dh->ref;
}

sub make_handle
{
	my $self = shift;
	return $self->make(ABO::DocHandle, $self, @_);
}

sub make_document
{
	my $self = shift;
	my $file = shift;
	local $x = $self->scope_error_func(sub {
		$self->error("\"$file\": ", @_);
	});
	return $self->make(ABO::Document, $self, $file);
}

sub add_document
{
	my $self = shift;
	my $doc = shift;
	my $dh = $doc->handle;

	local $x = $self->scope_error_func(sub {
		$self->error("$dh: ", @_);
	});
	my $file = $dh->file;
	$self->error("reference already used"), return undef
		if -s $file;
	local *DOC;
	open DOC, ">$file" or
		$self->error("cannot create `$file' - $!"), return undef;
	print DOC $doc->body;
	close DOC;
	utime time(), $doc->mtime, $file or
		$self->error("cannot set mtime of `$file' - $!"), return undef;
	return $file;
}

sub get_document
{
	my $self = shift;
	my $dh = $self->_get_handle(\@_) or return undef;
	return undef unless -s $dh->file;
	return $self->make(ABO::Document, $dh);
}

sub delete_document
{
	my $self = shift;
	my $dh = $self->_get_handle(\@_) or return undef;
	local $x = $self->scope_error_func(sub {
		$self->error("$dh: ", @_);
	});
	my $file = $dh->file;
	truncate $file, 0 or
		$self->error("cannot truncate file `$file' - $!"), return undef;
	return 1;
}

sub set_document_mtime
{
	my $self = shift;
	my $mtime = shift;
	my $dh = $self->_get_handle(\@_) or return undef;
	local $x = $self->scope_error_func(sub {
		$self->error("$dh: ", @_);
	});
	my $file = $dh->file;
	utime time(), $mtime, $file or
		$self->error("cannot set mtime of `$file' - $!"), return undef;
	return 1;
}

sub _all_refs
{
	my $self = shift;
	my $doctype = shift;
	my $dir = $self->doctype_dir($doctype) or return ();
	local *DIR;
	opendir DIR, $dir or
		$self->error("cannot open directory `$dir' - $!"), return ();
	my @refs = grep { !/^\./ && -f "$dir/$_" } readdir DIR;
	closedir DIR;
	return @refs;
}

sub _all_handles
{
	my $self = shift;
	my $doctype = shift;
	return grep { defined }
		map { $self->make_handle($doctype, $_) }
		$self->_all_refs($doctype);
}

sub _all_files
{
	my $self = shift;
	my $doctype = shift;
	return map { $_->file } $self->_all_handles($doctype);
}

sub handles
{
	my $self = shift;
	my $doctype = shift;
	return grep { -s $_->file } $self->_all_handles($doctype);
}

sub refs
{
	my $self = shift;
	my $doctype = shift;
	return map { $_->ref } $self->handles($doctype);
}

sub files
{
	my $self = shift;
	my $doctype = shift;
	return map { $_->file } $self->handles($doctype);
}

sub doctype_dir
{
	my $self = shift;
	my $doctype = shift;
	my $dir = $self->{'docdirs'}->{$doctype};
	$self->error("invalid doctype `$doctype'") unless defined $dir;
	return $dir;
}

##############################################################################
# Private methods.

sub _get_handle
{
	my $self = shift;
	my $a = shift;
	if (@$a >= 1 && UNIVERSAL::isa($a->[0], ABO::DocHandle))
	{
		return shift @$a;
	}
	elsif (@$a >= 1 && defined($a->[0]))
	{
		return $self->make_handle(shift @$a);
	}
	confess "bad args";
}

sub _alloc_handle
{
	my $self = shift;
	my $doctype = shift;
	return $self->make_handle($doctype, '') or die;
}

1;
