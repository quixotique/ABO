##############################################################################
package ABO::TransBase_Cache::Handle;

use overload
	'""' => "as_string",
	'bool' => "as_bool",
	;

sub new
{
	my $class = CORE::shift;
	my $self = bless [_flatten(@_)], ref($class) || $class;
	return $self;
}

sub _flatten
{
	my @r = ();
	push @r, ref($_) eq 'ARRAY' ? _flatten(@$_) : $_ foreach @_;
	return @r;
}

sub clone
{
	my $self = CORE::shift;
	return bless [@$self], ref($self);
}

sub push
{
	my $self = CORE::shift;
	push @$self, _flatten(@_);
	return $self;
}

sub pop
{
	my $self = CORE::shift;
	return pop @$self;
}

sub shift
{
	my $self = CORE::shift;
	return CORE::shift @$self;
}

sub last
{
	my $self = CORE::shift;
	return $self->[$#$self];
}

sub as_string
{
	my $self = CORE::shift;
	return join '|', @$self;
}

sub as_bool
{
	my $self = CORE::shift;
	return @$self != 0;
}

##############################################################################
package ABO::TransBase_Cache::TransBase;

use ABO::TransBase;
@ISA = qw(
	ABO::TransBase
);

sub new
{
	my $class = shift;
	my $self = bless {
			handle => $_[0],
			mtime => $_[1],
			parts => $_[2],
		}, ref($class) || $class;
	return $self;
}

sub handle { $_[0]->{'handle'} }
sub get_handles { keys %{$_[0]->{'parts'}} }
sub mtime { $_[0]->{'mtime'} }
sub fetch
{
	my ($self, $handle) = @_;
	my $val = $self->{'parts'}->{$handle};
	$val = $self->{'parts'}->{$handle} = &$val() if ref($val) eq 'CODE';

	# Cope with transaction sources that suddenly dissapear.
	delete $self->{'parts'}->{$handle} if !defined $val;

	return $val;
}

##############################################################################
package ABO::TransBase_Cache::TransSource;

use ABO::TransSource;
@ISA = qw(
	ABO::TransSource
);

sub new
{
	my $class = shift;
	my $self = bless {
			handle => $_[0],
			mtime => $_[1],
			transactions => $_[2],
		}, ref($class) || $class;
	return $self;
}

sub handle { $_[0]->{'handle'} }
sub mtime { $_[0]->{'mtime'} }
sub transactions { @{$_[0]->{'transactions'}} }
sub unsorted_transactions { $_[0]->transactions }

##############################################################################
package ABO::TransBase_Cache;

use ABO::Base;
use ABO::TransBase;
@ISA = qw(
	ABO::Base
	ABO::TransBase
);

use Carp qw(confess);
use FileHandle;
use GDBM_File;
use DB_File;
use Fcntl;

sub init
{
	my ($self, %args) = @_;
	confess "missing -file arg" unless defined $args{'-file'};
	confess "missing -source arg" unless defined $args{'-source'};
	my $dbfile = $args{'-file'};
	my $ts = $args{'-source'};
	confess "not a TransSource" unless UNIVERSAL::isa($ts, ABO::TransSource);

	unlink $dbfile if $self->_nucleus->option('regenerate-cache');

	my $dbobj;
	my $ext = $dbfile =~ /\.[^.]+$/o ? $& : '';
	if ($ext eq '.gdbm')
	{
		#unlink $dbfile;
		$dbobj = tie %{$self->{'db'}}, GDBM_File, $dbfile,
			&GDBM_WRCREAT, 0640;
	}
	elsif ($ext eq '.db')
	{
		#unlink $dbfile;
		$dbobj = tie %{$self->{'db'}}, DB_File, $dbfile,
			O_RDWR|O_CREAT, 0640, $DB_HASH;
	}
	else
	{
		$self->error("cannot tie to `$dbfile' - unknown extension `$ext'");
		return undef;
	}

	if (!$dbobj)
	{
		$self->error("cannot tie to `$dbfile' - $!");
		return undef;
	}

	$self->{'ts'} = $ts;
	$self->{'dbfile'} = $dbfile;
	$self->{'mtime'} = $self->_db->{'mtime'} || 0;

	return $self;
}

sub DESTROY
{
	my $self = shift;

	# In Perl 5.6.0 and earlier versions, a strange thing happens
	# with DB_File and GDBM_File tied hashes at this point: the tie
	# object, whether returned by the 'tied' operator or saved when
	# the 'tie' operator was called, appears undefined.  God knows
	# how this happens, but it looks like a bug in Perl.
	# Furthermore, attempting to untie in this situation causes Perl
	# to dump core.

	my $dbo = tied %{$self->{'db'}};
	if ($dbo)
	{
		$dbo->sync;
		undef $dbo;
		untie %{$self->{'db'}};
	}
}

sub _ts { $_[0]->{'ts'} }
sub _db { $_[0]->{'db'} }
sub _dbfile { $_[0]->{'dbfile'} }

################################################
# Implementation of "TransBase" interface.

sub handle
{
	return 'cache='.$_[0]->_dbfile;
}

sub get_handles
{
	return (new ABO::TransBase_Cache::Handle ($_[0]->_ts->handle));
}

sub mtime
{
	return $_[0]->_ts->mtime;
}

sub fetch
{
	my ($self, $h) = @_;
	return $self->_fetch($h, $self->_ts);
}

################################################
# Private methods.

sub _fetch
{
	my ($self, $handle, $ts) = @_;
	confess "bad arg 1" unless UNIVERSAL::isa($handle, ABO::TransBase_Cache::Handle);

#print STDERR "_fetch($handle)\n";

	# If we are fetching a cache entry for trans-source that no
	# longer exists, then we gripe about it and return undef to give
	# our caller a chance to amend their list of handles.
	$self->error("caching non-existent transaction source `",
			$handle->last, "'"
		),
		return undef
		unless defined $ts;
	confess "bad arg 2" unless UNIVERSAL::isa($ts, ABO::TransSource);

	# Don't ever cache "virtual" transaction bases or sources, and
	# delete any that may have become virtual since their last cache
	# hit.
	my $mtime = $ts->mtime;
	if (defined $mtime)
	{
		$tsc = $self->_cache_get($handle, $ts);
		my $cmtime = defined($tsc) ? $tsc->mtime : undef;
		if (defined($cmtime) && $cmtime >= $mtime)
		{
			$self->blah("fetch ", $handle->last, " from cache",
					" `", $self->_dbfile, "'"
				) if !UNIVERSAL::isa($tsc, ABO::TransBase);
			return $tsc;
		}
		$self->_cache_put($handle, $ts);
	}
	else
	{
		$self->_cache_delete($handle);
	}

	return $self->_fake_transbase($ts, $handle, $mtime, $ts->get_handles)
		if $ts->isa(ABO::TransBase);
	return $ts;
}

sub _cache_get
{
	my ($self, $h, $ts) = @_;
	my $key = "$h"; # stringify cache handle

	# To work around a wierd SEGV bug in DB_File, fetch the string
	# once first.
	my $_kludge = $self->_db->{$key};

	# Fetch the cache entry.
	my $ent = $self->_db->{$key};
	return undef unless defined $ent;

#print STDERR "_cache_get($key) hit\n";

	# Construct a "fake" TransBase or TransSource object from the
	# seralized cache entry.  Silently return a null result if the
	# serialization appears corrupt.
	my @lines = split /\n/, $ent;
	return undef unless @lines >= 3;
	my $type = shift @lines;
	my $mtime = shift @lines;
	undef $mtime unless length($mtime);
	return $self->_fake_transbase($ts, $h, $mtime, @lines) if
		$type eq 'base';
	return $self->_fake_transsource($ts, $h, $mtime, @lines) if
		$type eq 'source';
	return undef;
}

sub _cache_put
{
	my ($self, $h, $ts) = @_;
	my $key = "$h"; # stringify cache handle

	# Copy a TransBase or TransSource object into a "fake" object,
	# and serialize it into the cache.

	my @lines = ();
	my $mtime = $ts->mtime;
	$mtime = '' unless defined $mtime;
	if ($ts->isa(ABO::TransBase))
	{
		@lines = ('base', $mtime, $ts->get_handles);
	}
	else
	{
		my @trans = $ts->transactions;
		# We don't cache documents with no transactions --
		# possibly such documents have failed to parse, so we
		# should keep trying to parse them to elicit the parse
		# error messages until the user fixes the problem.
		@lines = ('source', $mtime, map { $_->serialize } @trans) if @trans;
	}

#print STDERR "_cache_put($key)\n";

	# Put or delete the cache entry;
	if (@lines)
	{
		$self->_db->{$key} = join "\n", @lines;
	}
	else
	{
		delete $self->_db->{$key};
	}
}

sub _cache_delete
{
	my ($self, $h) = @_;
	my $key = "$h"; # stringify cache handle
#print STDERR "_cache_delete($key)\n";
	# Delete the cache entry.
	delete $self->_db->{$key};
}

sub _fake_transbase
{
	my ($self, $tb, $handle, $mtime, @handles) = @_;
	my %parts = ();
	for my $h (@handles)
	{
		my $hh = $handle->clone->push("$h");
		$parts{$h} = sub { $self->_fetch($hh, $tb->fetch($h)); };
	}
	return new ABO::TransBase_Cache::TransBase
		($tb->handle, $mtime, \%parts);
}

sub _fake_transsource
{
	my ($self, $ts, $handle, $mtime, @transdump) = @_;

	## This object and all objects created by it (transactions) must
	## always report errors prefixed with the identity of this
	## document.
	#my $h = $handle->last;
	#my $tempnuc = $self->_nucleus->fork;
	#$tempnuc->fork_error_reporter->push_error_func(sub {
	#	$self->error("$h (cached): ", @_);
	#});

	# Suppress "invalid transaction" messages while we convert the
	# serialized cache transactions into transaction objects.
	local $x = $self->scope_error_func(sub {});

	my @trans = ();
	foreach (@transdump)
	{
		my $t = $self->make(ABO::Transaction, -serialized => $_)
			or return undef;
		push @trans, $t;
	}
	return new ABO::TransBase_Cache::TransSource
		($ts->handle, $mtime, \@trans);
}

1;
