package ABO::FilterList;
use feature 'unicode_strings';

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use ABO::Utils qw(argv);
use Getopt::Long;

sub init
{
	shift->_readfilterfile(@_);
}

sub _readfilterfile
{
	my $self = shift;

	my $fifile = $self->_config->varx('filter_file') or return undef;
	if (!open FIFILE, $fifile)
	{
		$self->error("cannot read `$fifile' - $!");
		return undef;
	}
	my @flist;
	my $line = 0;
	local $x = $self->scope_error_func(sub {
		$self->error("\"$fifile\" line $line: ", @_);
	});
	while (<FIFILE>)
	{
		$line++;
		chomp;
		next if !length || /^#/o;
		local @args = argv($_);
		my $fname = $args[0];
		$self->error("malformed filter name `$fname'"), return undef unless
			defined $fname && $fname =~ /^[A-Za-z_]+$/o;
		eval "require ABO::Filter$fname";
		$self->error("non-existent filter `$fname'"), return undef if $@;
		push @flist, \@args;
	}
	close FIFILE;
	$self->{'flist'} = \@flist;
	return $self;
}

sub filters
{
	my $self = shift;
	return @{$self->{'flist'}};
}

sub filter
{
	my ($self, $ts) = @_;
	for my $fi ($self->filters)
	{
		my @args = @$fi;
		my $filter_name = 'ABO::Filter'.shift(@args);
		$ts = $self->make($filter_name, -source => $ts, @args) or return undef;
	}
	return $ts;
}

1;
