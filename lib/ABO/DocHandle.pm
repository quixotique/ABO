package ABO::DocHandle;
use feature 'unicode_strings';

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use Carp qw(confess cluck);

use overload
	'""' => "as_string",
	'bool' => sub { 1; },
	eq => "equals",
	ne => "not_equal",
	;

##############################################################################
# Public methods.

sub init
{
	my ($self, $docbase) = splice @_, 0, 2;
	confess "bad arg 1" unless UNIVERSAL::isa($docbase, ABO::DocBase);
	my ($doctype, $ref);
	if (@_ == 1 && $_[0] =~ /^(\S+) (.*)$/o)
	{
		# Accept a stringified DocHandle.
		$doctype = $1;
		$ref = $2;
	}
	elsif (@_ == 1 && UNIVERSAL::isa($_[0], __PACKAGE__))
	{
		# Accept another DocHandle.
		$doctype = $_[0]->doctype;
		$ref = $_[0]->ref;
		confess "doctype undefined" unless defined $doctype;
		confess "ref undefined" unless defined $ref;
	}
	elsif (@_ == 2 && defined($_[0]) && defined($_[1]))
	{
		# Accept a doctype string and a ref string (an empty ref
		# string means allocate a new ref).
		$doctype = $_[0];
		$ref = $_[1];
	}
	else
	{
		confess "bad args";
	}

	# Perform validity checks on doctype.
	$self->{'docdir'} = $docbase->doctype_dir($doctype) or return undef;
	$self->{'doctype'} = $doctype;
	$self->{'reftem'} = $self->_config->var($doctype.'_ref');
	return undef unless defined $self->_reftem;

	# Setup ref.
	if (length $ref)
	{
		my $file = $self->_docdir.'/'.$ref;
		$self->error("$doctype ref `$ref' not allocated"), return undef
			unless -f $file && -r _;
		$self->{'ref'} = $ref;
		$self->{'file'} = $file;
	}
	else
	{
		$self->_alloc_ref or return undef;
	}

#print STDERR "init: ", join("\n      ", map { "$_=>".$self->{$_} } keys %$self), "\n";
	return $self;
}

sub doctype
{
	return shift->{'doctype'};
}

sub ref
{
	return shift->{'ref'};
}

sub file
{
	return shift->{'file'};
}

sub as_string
{
	my $self = shift;
	my $doctype = $self->doctype;
	my $ref = $self->ref;
	$doctype = 'UNDEF' if !defined $doctype;
	$ref = 'UNDEF' if !defined $ref;
	return $doctype.' '.$ref;
}

sub equals
{
	my ($a, $b) = @_;
	return $a->doctype eq $b->doctype && $a->ref eq $b->ref;
}

sub not_equal
{
	return !shift->equals(@_);
}

##############################################################################
# Private methods.

sub _docdir		{ shift->{'docdir'} }
sub _reftem		{ shift->{'reftem'} }

sub _alloc_ref
{
	my $self = shift;

	# There is a race condition here that should be excluded by a
	# lock.

	# Generate a ref for a document file that does not yet exist.
	my $reftem_alloc = $self->_mk_ref($self->_reftem);
	my $rexp_alloc = _mk_rexp($reftem_alloc);
	my $docdir = $self->_docdir;
	my $ref;
	my $file;
	do {
		$ref = $self->_mk_ref(
			$reftem_alloc,
			defined($ref) && $ref =~ $rexp_alloc ? $1 + 1 : 1
		);
		$file = $docdir.'/'.$ref;
	}
		while -f $file;

	# Create the file with zero length to allocate it.
	local *ID;
	if (!open ID, ">$file")
	{
		$self->error("cannot create `$file' - $!");
		return undef;
	}
	close ID;

	$self->{'ref'} = $ref;
	$self->{'file'} = $file;

	return $self;
}

# Generate ref string from template string.
sub _mk_ref
{
	my $self = shift;
	my $tem = shift;

	my @t = $self->_nucleus->today->tm;
	my $de = $self->_nucleus->today - $self->_nucleus->epoch;
	my %e = ();
	$e{Y} = sprintf "%u", $t[5] % 10;
	$e{YY} = sprintf "%02u", $t[5] % 100;
	$e{YYY} = sprintf "%03u", $t[5];
	$e{YYYY} = sprintf "%04u", $t[5] + 1900; # Oops, Y10K bug!
	$e{M} = sprintf "%u", $t[4] + 1;
	$e{MM} = sprintf "%02u", $t[4] + 1;
	$e{D} = sprintf "%u", $t[3];
	$e{DD} = sprintf "%02u", $t[3];
	$e{E} = sprintf "%u", $de;
	$e{EE} = sprintf "%02u", $de;
	$e{EEE} = sprintf "%03u", $de;
	$e{EEEE} = sprintf "%04u", $de;
	$e{EEEEE} = sprintf "%05u", $de;
	$e{EEEEEE} = sprintf "%06u", $de;
	$e{EEEEEEE} = sprintf "%07u", $de;
	if (@_)
	{
		my $iter = shift;
		$e{I} = sprintf "%u", $iter;
		$e{II} = sprintf "%02u", $iter;
		$e{III} = sprintf "%03u", $iter;
		$e{IIII} = sprintf "%04u", $iter;
		$e{IIIII} = sprintf "%05u", $iter;
	}
	my $re = join '|', keys %e;
	$tem =~ s/{($re)}/ $e{$1} /eg;
	return $tem;
}

# Static private method.
sub _mk_rexp
{
	my $f = shift;

	my %e = ();
	$e{Y} = '\d{1}';
	$e{YY} = '\d{2}';
	$e{YYY} = '(?:0|1)\d{2}';
	$e{YYYY} = '(?:19[789]\d|2\d{3})'; # Oops, Y10K bug!
	$e{M} = '\d+';
	$e{MM} = '\d{2}';
	$e{D} = '\d+';
	$e{DD} = '\d{2}';
	$e{E} = '(\d+)';
	$e{EE} = '(\d{2,})';
	$e{EEE} = '(\d{3,})';
	$e{EEEE} = '(\d{4,})';
	$e{EEEEE} = '(\d{5,})';
	$e{EEEEEE} = '(\d{6,})';
	$e{EEEEEEE} = '(\d{7,})';
	$e{I} = '(\d+)';
	$e{II} = '(\d{2,})';
	$e{III} = '(\d{3,})';
	$e{IIII} = '(\d{4,})';
	$e{IIIII} = '(\d{5,})';
	my $re = join '|', keys %e;
	$f =~ s/{($re)}|./ (defined($1) && $e{$1}) || quotemeta $& /eg;
	return qr/^$f$/;
}

1;
