package ABO::Book;
use feature 'unicode_strings';

use ABO::Base;
use ABO::TransSource;
@ISA = qw(
	ABO::Base
	ABO::TransSource
);

use Cwd ();

sub init
{
	my ($self, %args) = @_;
	my $book = $args{'-name'};
	local $_;

	# Each book has its own configuration and error reporting
	# settings, so we fork the nucleus (shallow copy) then fork its
	# configuration object and error reporter object, so we can then
	# alter them without affecting the rest of the ABO.

	my $onucleus = $self->_nucleus;
	$self->_fork_nucleus;
	$self->_nucleus->fork_error_reporter;
	$self->_nucleus->fork_config;
	
	# Prefix all errors reported by this book's objects with the
	# identity of this book.

	$self->push_error_func(
		sub { $self->error("book \"$book\": ", @_); }
	);

	# Locate the base directory for this book.

	my $bookdir = $self->_config->varx('book_'.$book.'_dir');
	if (!defined $bookdir)
	{
		$bookdir = $self->_config->varx('book_dir') or
			$self->_config->var_error_undef(
				'book_'.$book.'_dir',
				'book_dir',
			),
			return undef;
		$bookdir .= '/'.$book;
	}
	$self->error("book directory `$bookdir' does not exist"), return undef
		unless -d $bookdir;

	# Set up the configuration specific to this book.

	$self->_config->parse_file($bookdir.'/.bookrc')
		or return undef;
	$self->{'book'} = $book;
	$self->{'bookdir'} = $bookdir;
	my $open_date = $self->_config->var_date('open_date');
	my $close_date = $self->_config->var_date('close_date');
	return undef unless defined $open_date && defined $close_date;
	$self->{'open_date'} = $open_date;
	$self->{'close_date'} = $close_date;
	
	# Set up the link to the previous book (if any) and check that
	# its close date fits with our open date.

	my $prevbook = $self->_config->varx('previous_book');
	my $prevts;
	if (defined $prevbook)
	{
		$prevts = $onucleus->make(ABO::Book, -name => $prevbook)
			or return undef;
		$self->error("invalid open date $open_date - precedes close date ",
				$prevts->close_date,
				" of previous book ($prevbook)"
			), return undef
			if $open_date <= $prevts->close_date;
		$self->error("Warning: open date $open_date does not immediately follow close date ",
				$prevts->close_date,
				" of previous book ($prevbook)"
			)
			if $open_date != $prevts->close_date + 1;
	}

	# Transactions in this book are subject to certain extra
	# constraints...  specifically, they must lie within the book's
	# open and close dates.

	$self->_nucleus->set_transaction_validator(sub{
		my $t = shift;
		my $msg;
		my $d = $t->date;
		if ($d < $open_date)
		{
			$msg = "before book open date ".$self->open_date;
		}
		elsif ($d > $close_date)
		{
			$msg = "after book close date ".$self->close_date;
		}
		else
		{
			return $t;
		}
		$t->error("illegal transaction date `", $t->date, "' - $msg");
		return undef;
	});

	# Set up sources of transactions in this book.
	my @ts = ();
	my $ts;

	# The principal transaction source - DocBase.
	$ts = $self->{'docbase'} = $self->make(ABO::DocBase, -dir => $bookdir);
	push @ts, $ts if $ts;

	# An optional transaction source - file or command output.
	$_ = $self->_config->varx("transaction_src");
	if (defined($_) && /^!/o)
	{
		$ts = $self->make(ABO::TransSource_Cmd, -exec => substr($_, 1));
	}
	elsif (defined $_)
	{
		$ts = $self->make(ABO::TransSource_File, -file => $_);
	}
	push @ts, $ts if $ts;

	# Join them (even if there is only one -- to keep consistent
	# TransBase cache indexing).
	$self->error("no source of transactions"), return undef
		unless @ts;
	$ts = $self->make(ABO::TransBase_Concat,
			-name => $book,
			-sources => \@ts
		);

	# Start the TransBase cache (if there is a file for it).
	defined($_ = $self->_config->varx("document_cache"))
		and $_ = $self->make(ABO::TransBase_Cache,
				-file => $_,
				-source => $ts,
			)
		and $ts = $_;

	# Start the Transaction cache (if there is a file for it).
	defined($_ = $self->_config->varx("transaction_cache"))
		and $_ = $self->make(ABO::TransSource_Cache,
				-file => $_,
				-source => $ts
			)
		and $ts = $_;

	my $bts = $ts;

	# Set up transaction sources that include transactions from the
	# previous book.  We make two alternative sources: one that
	# simply concatenates the previous book with this book, and one
	# for when the desired "from" date does not fall before this
	# book, in which case we don't need all of the previous book's
	# transactions, just a brought-forward summary of them.

	# These transaction sources will make transactions that violate
	# the transaction validation for the book established above.  So
	# we fork another nucleus, give it another transaction
	# validator, and use that nucleus to create these objects.
	#
	my $pnuc = $self->_nucleus->fork;
	$pnuc->set_transaction_validator(sub{
		my $t = shift;
		return $t if $t->date < $self->open_date;
		$t->error("illegal transaction date `",
			$t->date,
			"' - after book open date"
		);
		return undef;
	});

	my $allts = $bts;
	my $bfts;
	if ($prevts)
	{
		# If we have a previous book, use it.
		$allts = $self->make(ABO::TransBase_Concat,
				-name => $prevbook.'+'.$book,
				-sources => [ $prevts, $bts ],
				-concat => 1,
			) or return undef;
		$bfts = $pnuc->make(ABO::FilterCancelForward,
				-source => $prevts,
				-date => $prevts->close_date,
			)
			or return undef;
	}
	#
	# Whether or not there is a previous book, we open a cache of
	# its brought-forward transactions.  ABO::TransSource_Cache will
	# accept a null TransSource argument, so this handles the case
	# where the previous book has been removed, leaving just our
	# cache as the only remaining source of brought-forward
	# transactions.
	#
	defined($_ = $pnuc->_config->varx("broughtforward_cache"))
		and $_ = $pnuc->make(ABO::TransSource_Cache,
				-file => $_,
				-source => $bfts,
			)
		and $bfts = $_;
	if ($bfts)
	{
		$bfts = $self->make(ABO::TransBase_Concat,
				-name => $book.'-bf',
				-sources => [ $bfts, $bts ],
				-concat => 1,
			) or return undef;
	}
	else
	{
		$bfts = $bts;
	}
	$self->{'ts_all'} = $allts;
	$self->{'ts_bf'} = $bfts;
	$self->{'ts_prev'} = $prevts;

	return $self;
}

sub _tsource
{
	my ($self, $sorted, $from, $to) = @_;
	return $self->{'ts_prev'} if defined $to && $to < $self->open_date;
	$self->blah(
		"get $sorted transactions, book \"",
		$self->{'book'},
		"\", from=",
		$from ? $from : 'UNDEF',
		", to=",
		$to ? $to : 'UNDEF',
	);
	$self->{defined $from && $from >= $self->open_date ? 'ts_bf' : 'ts_all'};
}

sub handle	{ 'book='.$_[0]->{'book'} }
sub mtime	{ $_[0]->{'ts_all'}->mtime; }

sub unsorted_transactions
{
	my $self = shift;
	my ($from, $to) = @_;
	my $ts = $self->_tsource("unsorted", @_) or return ();
	$ts->unsorted_transactions(@_);
}

sub transactions
{
	my $self = shift;
	my ($from, $to) = @_;
	my $ts = $self->_tsource("sorted", @_) or return ();
	$ts->transactions(@_);
}

sub docbase	{ $_[0]->{'docbase'}; }

sub open_date	{ $_[0]->{'open_date'}; }
sub close_date	{ $_[0]->{'close_date'}; }

1;
