package ABO::AccountList;
use feature 'unicode_strings';

use ABO::Base;
@ISA = qw(
	ABO::Base
);

sub init
{
	shift->_readacfile(@_);
}

sub _readacfile
{
	my $self = shift;

	my $acfile = $self->_config->var('account_file') or return undef;
	if (!open ACFILE, $acfile)
	{
		$self->error("cannot read `$acfile' - $!");
		return undef;
	}
	my %aclist;
	my $line = 0;
	local $x = $self->scope_error_func(sub {
		$self->error("\"$acfile\" line $line: ", @_);
	});
	while (<ACFILE>)
	{
		$line++;
		chomp;
		next if !length || /^#/o;
		my $a = $self->make(ABO::Account, $_) or return undef;
		$aclist{$a->name} = $a;
	}
	close ACFILE;
	$self->{'aclist'} = \%aclist;
	return $self;
}

sub accounts
{
	my $self = shift;
	return values %{$self->{'aclist'}};
}

sub get_account_byname
{
	my $self = shift;
	return $self->{'aclist'}->{shift()};
}

1;
