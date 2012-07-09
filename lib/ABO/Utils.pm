# Utilities for ABO programming.
use feature 'unicode_strings';

package ABO::Utils;

use Carp qw(confess);

require Exporter;
@ISA = qw(Exporter);
@EXPORT_OK = qw(
	empty
	trim
	concat
	pick
	swap
	rotleft
	rotright
	min
	max
	fmtamt
	fmtwamt
	fmtpar
	fmtwid
	centrestr
	fromtostr
	similar
	wrap
	argv
	system_io
);
%EXPORT_TAGS = (
	'all' => \@EXPORT_OK,
	'string' => [qw(
		empty
		trim
		concat
		pick
		centrestr
		fromtostr
		argv
	)],
	'array' => [qw(
		pick
		swap
		rotleft
		rotright
	)],
	'format' => [qw(
		fmtamt
		fmtwamt
		fmtpar
		fmtwid
		centrestr
		fromtostr
		similar
		wrap
	)],
	'io' => [qw(
		system_io
	)],
);

sub empty ($) { !defined $_[0] || length $_[0] == 0 }
sub trim ($) { local $_ = shift; s/^\s+//o; s/\s+$//o; s/\s{2,}/ /og; $_; }
sub concat (@) { trim join ' ', grep { defined } @_; }
sub pick (@) { shift @_ while @_ > 1 && !defined $_[0]; $_[0]; }
sub swap ($$) { @_[0, 1] = @_[1, 0] }
sub rotleft (@) { my $t = shift @_; push @_, $t; @_ }
sub rotright (@) { my $t = pop @_; unshift @_, $t; @_ }

sub min ($@)
{
	my $m = shift;
	$m = $_ < $m ? $_ : $m foreach @_;
	return $m;
}

sub max ($@)
{
	my $m = shift;
	$m = $_ > $m ? $_ : $m foreach @_;
	return $m;
}

sub fmtpar
{
	my $r = "$_[0]";
	return $r =~ /^-/o ? "($')" : "$r ";
}

sub fmtwamt
{
	return &fmtwid(@_[0, 1]);
}

sub fmtwid
{
	my $s = "$_[0]";
	my $w = $_[1];
	return defined($w) && length($s) > $w ? '*' x $w : $s;
}

sub centrestr
{
	my ($w, $s) = @_;
	return $s if length($s) >= $w;
	return (' ' x (($w - length($s)) / 2)).$s;
}

sub fromtostr
{
	my ($from, $to) = @_;
	return join ' ',
		$from ne '.' ? 'FROM '.$from->format('%-d-%b-%Y') : '',
		$to ne '.' ? 'TO '.$to->format('%-d-%b-%Y') : '';
}

sub similar
{
	my ($a, $b) = (trim($_[0]), trim($_[1]));
	my $lim = max(int(max(length($a), length($b)) * .8), 3);
	while (length($a) && length($b))
	{
		last if $lim-- == 0;
		return 0 if uc(substr($a, 0, 1)) ne uc(substr($b, 0, 1));
		$a = substr($a, 1);
		$b = substr($b, 1);
	}
	return 1;
}

sub wrap
{
	my @s = ((split /\s+/, shift), '');
	my $n = shift;
	my $t = '';
	my $w = '';
	my @r = ();
	while (length($w) || defined($w = shift @s))
	{
		if (length($t) + 1 >= $n)
		{
			push @r, $t;
			$t = '';
		}
		else
		{
			my $sp = (length $t && length $w ? 1 : 0);
			if (length($w) && length($t) + $sp + length($w) <= $n)
			{
				$t .= ' ' if $sp;
				$t .= $w;
				$w = '';
			}
			else
			{
				if (length($w) > $n)
				{
					$t .= ' ' if $sp;
					my $l = $n - length($t);
					$t .= substr($w, 0, $l);
					$w = substr($w, $l);
				}
				push @r, $t;
				$t = '';
			}
		}
	}
	return @r;
}

sub argv
{
	my @c = split //, $_[0];
	my @arg = ();
	my @argv = ();
	my $havearg;
	my $slosh;
	my $quote;
	while (@c)
	{
		my $c = shift @c;
		if ($slosh)
		{
			push @arg, '\\';
			undef $slosh;
		}
		elsif ($c eq '\\')
		{
			$slosh = 1;
		}
		elsif (defined $quote)
		{
			if ($c eq $quote)
			{
				undef $quote;
			}
			else
			{
				push @arg, $c;
			}
		}
		elsif ($c eq '"' || $c eq "'")
		{
			$quote = $c;
			$havearg = 1;
		}
		elsif ($c =~ /\s/o)
		{
			push @argv, join('', @arg) if @arg || $havearg;
			@arg = ();
			undef $havearg;
		}
		else
		{
			push @arg, $c;
		}
	}
	push @argv, join('', @arg) if @arg || $havearg;
	return @argv;
}


use Fcntl;
use IPC::Open3;

sub system_io
{
	my ($cmd, $stdin, $rstdout, $rstderr) = @_;

	my @cmd = ref $cmd eq 'ARRAY' ? @$cmd : ($cmd);
	my $inoff = 0;
	my $stdout = '';
	my $stderr = '';
	local (*IN, *OUT, *ERR);
	my $pid = open3(IN, OUT, ERR, @cmd);
	my $in_fd = fileno IN;
	my $out_fd = fileno OUT;
	my $err_fd = fileno ERR;
	my $rin = '';
	my $win = '';
	my $rout;
	my $wout;
	my $eout;
	if (defined $stdin)
	{
		vec($win, $in_fd, 1) = 1;
		fcntl IN, F_SETFL, O_NONBLOCK or die;
	}
	else
	{
		vec($win, $in_fd, 1) = 0;
		close IN;
	}
	if (defined $rstdout)
	{
		vec($rin, $out_fd, 1) = 1;
	}
	else
	{
		vec($rin, $out_fd, 1) = 0;
		close OUT;
	}
	if (defined $rstderr)
	{
		vec($rin, $err_fd, 1) = 1;
	}
	else
	{
		vec($rin, $err_fd, 1) = 0;
		close ERR;
	}
	while (	(unpack("b*", $rin) + 0 || unpack("b*", $win) + 0)
	   &&	select($rout = $rin, $wout = $win, $eout = $rin | $win, undef)
	)
	{
		#warn "rin=", unpack('b*', $rin),
		#	" win=", unpack('b*', $win),
		#	" rout=", unpack('b*', $rout),
		#	" wout=", unpack('b*', $wout),
		#	" eout=", unpack('b*', $eout),
		#	"\n";
		local $/ = undef;
		if (vec($wout, $in_fd, 1) && $inoff < length $stdin)
		{
			#warn "write IN\n";
			$inoff += syswrite IN, $stdin, length $stdin, $inoff;
		}
		if (vec($rout, $out_fd, 1))
		{
			#warn "read OUT\n";
			sysread OUT, $stdout, 1024, length $stdout
				or vec($eout, $out_fd, 1) = 1;
		}
		if (vec($rout, $err_fd, 1))
		{
			#warn "read ERR\n";
			sysread ERR, $stderr, 1024, length $stderr
				or vec($eout, $err_fd, 1) = 1;
		}
		if (	(vec($win, $in_fd, 1) && $inoff >= length $stdin)
		   ||	vec($eout, $in_fd, 1))
		{
			#warn "close IN\n";
			vec($win, $in_fd, 1) = 0;
			close IN;
		}
		if (vec($eout, $out_fd, 1))
		{
			#warn "close OUT\n";
			vec($rin, $out_fd, 1) = 0;
			close OUT;
		}
		if (vec($eout, $err_fd, 1))
		{
			#warn "close ERR\n";
			vec($rin, $err_fd, 1) = 0;
			close ERR;
		}
	}
	$$rstdout = $stdout if defined $rstdout;
	$$rstderr = $stderr if defined $rstderr;
	return waitpid($pid, 0) == $pid ? $? : undef;
}

1;
