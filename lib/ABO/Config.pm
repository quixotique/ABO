package ABO::Config;

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use File::Basename;

##############################################################################
# Public methods.

sub init
{
	my ($self, $pwd) = @_;
	$pwd =~ s!/+$!!o;
	$self->{'config'} = {};
	return $self->_readconfig($pwd);
}

sub parse_file
{
	my ($self, $file) = @_;
	_readrc($file, $self->{'config'}) or
		$self->error("cannot read `$file' - $!"), return undef;
	return $self;
}

sub clone
{
	my $self = shift;
	my $clone = $self->SUPER::clone;
	my %c = %{$self->{'config'}};
	$clone->{'config'} = \%c;
	return $clone;
}

sub vars
{
	my $self = shift;
	my %h = map { ($_ => $self->_value_of($_, 1) ) }
		keys %{$self->{'config'}};
	return \%h;
}

sub var { return shift->_value_of(shift, 0); }
sub varx { return shift->_value_of(shift, 1); }

sub var_date
{
	my $self = shift;
	my $var = shift;
	my $val = $self->_value_of($var, 0);
	return undef unless defined $val;
	local $x = $self->scope_error_func(sub {
		$self->var_error_invalid($var, @_);
	});
	return $self->make_date($val);
}

sub var_error_undef
{
	my $self = shift;
	$self->error(
		"configuration variable".(@_ == 1 ? '' : 's')." ".
		join(', ', map { "`$_'" } @_).
		" not defined"
	);
}

sub var_error_invalid
{
	my $self = shift;
	my $var = shift;
	$self->error($self->_details_of($var), "bad value of config variable '$var': ", @_);
}

##############################################################################
# Private methods.

sub _readconfig
{
	my ($self, $pwd) = @_;
	my $config = $self->{'config'};
	my $dir = '';
	my $gotrcfile;
	for (split /\/+/o, $pwd)
	{
		$dir .= $_.'/';
		$gotrcfile = 1 if _readrc($dir.'.aborc', $config);
	}
	$self->error("cannot find .aborc file"), return undef unless $gotrcfile;
	return $self;
}

sub _readrc
{
	my ($rcfile, $hr) = @_;
	local *RC;
	open RC, "<$rcfile" or return undef;
	$hr->{HERE} = [dirname($rcfile), undef, undef];
	my $line = 0;
	while (<RC>)
	{
		$line++;
		chomp;
		next unless /^(\w+)\s*(.*)$/o;
		$hr->{$1} = [_expand_vars($2, $hr), $rcfile, $line];
	}
	undef $hr->{HERE};
	close RC;
	return 1;
}

sub _expand_vars
{
	local $_ = shift;
	my $hr = shift;
	s/\\(\\|\$)|\$(\w+)|\${(\w+)}/
		defined($2) ? _expand($hr, $2) :
		defined($3) ? _expand($hr, $3) :
		$1
	/eog;
	return $_;
}

sub _expand
{
	my ($hr, $var) = @_;
	return $hr->{$var}->[0] if defined $hr->{$var};
	return $ENV{$var} if defined $ENV{$var};
	return '';
}

sub _value_of
{
	my $self = shift;
	my $v = shift;
	my $quiet = shift;
	my $val = $self->{'config'}->{$v};
	$self->var_error_undef($v) if !defined($val) && !$quiet;
	return $val && $val->[0];
}

sub _details_of
{
	my $self = shift;
	my $v = shift;
	my $val = $self->{'config'}->{$v} or return "";
	my @s = ();
	push @s, '"'.$val->[1].'"' if defined $val->[1];
	push @s, 'line '.$val->[2] if defined $val->[2];
	return @s ? join(' ', @s).': ' : '';
}

1;
