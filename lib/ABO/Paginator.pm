package ABO::Paginator;
use feature 'unicode_strings';

# Tie to a file handle to get support for paginated output.

sub TIEHANDLE
{
	my ($class, $out) = @_;
	bless {
		out_fh => $out,
		current_line => 0,
		lines_per_page => 0,
		nl => 0,
		ff => undef,
		header => undef,
		footer_lines => 0,
		footer => undef,
		in_headfoot => 0,
	}, $class;
}

sub lines_per_page
{
	my ($self, $val) = @_;
	$self->{lines_per_page} = $val + 0 if defined $val;
	$self->{lines_per_page};
}

sub ff_str
{
	my $self = shift;
	$self->{ff} = $_[0] if @_;
	$self->{ff};
}

sub header
{
	my ($self, $val) = @_;
	$self->{header} = $val if defined $val;
	$self->{header};
}

sub footer
{
	my $self = shift;
	$self->{footer_lines} = shift() + 0 if @_;
	$self->{footer} = shift() if @_;
	wantarray ? ($self->{footer_lines}, $self->{footer}) : $self->{footer_lines};
}

sub PRINT
{
	my $self = shift;
	local $_ = join('', @_);
	while (s/^(.*?)\r*\f//so)
	{
		$self->_printlines($1) or return undef;
		$self->_formfeed or return undef;
	}
	$self->_printlines($_);
}

sub need_lines
{
	my ($self, $need) = @_;
	if ($need <= $self->{lines_per_page})
	{
		if ($self->{current_line} + $need > $self->{lines_per_page} - $self->{footer_lines})
		{
			$self->_formfeed or return undef;
		}
	}
	1;
}

sub CLOSE
{
	my $self = shift;
	$self->_formfeed or return undef if $self->{current_line};
	undef $self->{out_fh};
	1;
}

sub DESTROY
{
	my $self = shift;
	$self->CLOSE if $self->{out_fh};
}

sub _printlines
{
	my ($self, $str) = @_;
	for my $line (split /\n/, $str, -1)
	{
		if (length $line)
		{
			$self->_print_header or return undef
				if $self->{current_line} == 0;
			$self->_flush_nl or return undef;
			print { $self->{out_fh} } $line or return undef;
		}
		$self->{nl}++;
		$self->{current_line}++;
	}
	$self->{nl}--;
	$self->{current_line}--;
	1;
}

sub _flush_nl
{
	my $self = shift;
	if ($self->{nl})
	{
		print { $self->{out_fh} } "\n" x $self->{nl} or return undef;
		$self->{nl} = 0;
	}
	1;
}

sub _formfeed
{
	my $self = shift;
	$self->_print_footer or return undef;
	if (defined $self->{ff})
	{
		print { $self->{out_fh} } $self->{ff} or return undef;
		$self->{nl} = 0;
	}
	else
	{
		$self->{nl} += $self->{lines_per_page} - $self->{current_line}
			if $self->{lines_per_page};
		$self->_flush_nl or return undef;
	}
	$self->{current_line} = 0;
	1;
}

sub _print_header
{
	my $self = shift;
	my $he = $self->{header};
	if (defined $he && !$self->{in_headfoot})
	{
		$self->{in_headfoot} = 1;
		if (ref $he eq 'CODE')
		{
			&$he();
		}
		else
		{
			$self->_printlines($he) or return undef;
		}
		$self->{in_headfoot} = 0;
	}
	1;
}

sub _print_footer
{
	my $self = shift;
	if (!$self->{in_headfoot})
	{
		if ($self->{lines_per_page})
		{
			my $fl = $self->{lines_per_page} - $self->{footer_lines};
			$self->{nl} += $fl - $self->{current_line};
			$self->{current_line} = $fl;
		}
		my $fo = $self->{footer};
		if (defined $fo)
		{
			$self->_flush_nl or return undef;
			$self->{in_headfoot} = 1;
			if (ref $fo eq 'CODE')
			{
				&$fo();
			}
			else
			{
				$self->_printlines($fo) or return undef;
			}
			$self->{in_headfoot} = 0;
		}
	}
	1;
}

sub PRINTF
{
	my $self = shift;
	my $fmt = shift;
	$self->PRINT(sprintf($fmt, @_));
}

# Syswrite bypasses pagination entirely.
#
sub WRITE
{
	my ($self, $data, $len, $off) = @_;
	syswrite $self->{out_fh}, $data, $len || length($data), $off || 0;
}

# All input requests are passed on.

sub READ
{
	my ($self, $buf, $len, $off) = @_;
	read $self->{out_fh}, $buf, $len, $off || 0;
}

sub READLINE
{
	my $self = shift;
	my $fh = $self->{out_fh};
	<$fh>;
}

sub GETC
{
	my $self = shift;
	getc $self->{out_fh};
}

1;
