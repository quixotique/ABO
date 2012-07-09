package ABO::Document;

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use ABO::Utils qw(empty);
use Carp;

# To add more document parsers, simply add them to this list and make
# sure they are a sub-class of this class.

my @document_parsers = (
	ABO::Document::Invoice_Groff,
	ABO::Document::Receipt_Groff,
	ABO::Document::Journal_Text,
);

my $documents_loaded;

sub init
{
	my $self = shift;
	confess "must override" unless ref($self) eq __PACKAGE__;
	my $handle;
	$self->_fork_nucleus;
	if (@_ == 1 && UNIVERSAL::isa($_[0], ABO::DocHandle))
	{
		# Document comes from within the document base, and is
		# identified by its handle.  The document will be parsed
		# later, but now we know its handle and hence its file
		# name.
		$handle = shift;
		$self->{'file'} = $handle->file;
	}
	elsif (@_ == 2 && UNIVERSAL::isa($_[0], ABO::DocBase) && defined($_[1]))
	{
		# Document comes from a named file outside the document
		# base.  We parse the document now and create a handle
		# for it.
		my $docbase = shift;
		$self->{'file'} = shift;
		my $parser = $self->_parser or return undef;
		$handle = $docbase->make_handle($parser->doctype, $parser->ref)
			or return undef;
	}
	else
	{
		confess "bad args";
	}
	$self->{'handle'} = $handle;

	# This document object and all objects created by it
	# (transactions) must always report errors prefixed with the
	# identity of this document.
	$self->_nucleus->fork_error_reporter->push_error_func(sub {
		$self->error("$handle: ", @_);
	});
	return $self;
}

##############################################################################
# Implement TransSource interface.

sub handle { shift->{'handle'} }

sub mtime
{
	my $self = shift;
	my $file = $self->file;
	my @s = stat $file or
		$self->error("cannot stat `$file' - $!"), return undef;
	return $s[9];
}

sub file { shift->{'file'} }

sub unsorted_transactions
{
	my $parser = shift->_parser;
	return $parser ? $parser->unsorted_transactions : ();
}

sub transactions
{
	my $parser = shift->_parser;
	return $parser ? $parser->transactions : ();
}

##############################################################################
# Other methods specific to documents.

sub body
{
	my $self = shift;
	my $body = $self->{'body'};
	return $body if defined $body;
	return $self->{'body'} = $self->_read_file;
}

sub attributes
{
	my $parser = shift->_parser;
	return $parser ? $parser->attributes : ();
}

sub attribute
{
	my $parser = shift->_parser;
	return $parser ? $parser->attribute(@_) : undef;
}

##############################################################################
# Private methods.

sub _parser
{
	my $self = shift;

	return $self->{'parser'} if exists $self->{'parser'};

	my $body = $self->body or return undef;
	my $dh = $self->handle;
	$self->blah("parse ", $dh || $self->file || '??');
	my $imp = _implementor($body, $dh && $dh->doctype) or
		$self->error("document not recognized"), return undef;
	my $parser = $self->{'parser'} = $self->make($imp, $body) or
		return undef;
	confess "bad type" if empty $parser->doctype;
	confess "bad ref" if empty $parser->ref;
	if (defined $dh)
	{
		my $ref = $parser->ref;
		$self->error("Warning: ref `$ref' is incorrect")
			if $ref ne $dh->ref;
	}
	return $parser;
}

sub _read_file
{
	my $self = shift;
	my $file = $self->file;

	local *DOC;
	open DOC, "<$file" or
		$self->error("cannot read `$file' - $!"), return undef;
	local $/ = undef;
	my $body = <DOC>; # slurp
	close DOC;
	$self->error("document `$file' is empty") unless defined $body;
	return $body;
}

# Static method.
sub _implementor
{
	my ($body, $doctype) = @_;
	_load_parsers();
	for (@document_parsers)
	{
		next unless $_->isa(ABO::Document::Parser);
		next if defined($doctype) && $doctype ne $_->doctype;
		return $_ if $_->probe($body);
	}
	return undef;
}

sub _load_parsers
{
	return if $documents_loaded;
	for my $class (@document_parsers)
	{
		eval "require $class";
		die $@ if $@;
	}
	$documents_loaded = 1;
}

1;
