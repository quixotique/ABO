package Groff::Parser;

# Author: Andrew Bettison <andrewb@zip.com.au>

use strict;

use vars qw($VERSION);
$VERSION = "1.00";


sub new
{
	my $class = shift;
	my $self = bless {}, ref($class) || $class;
	my %args = @_;
	$self->{__PACKAGE__.'.handler_text'} = $args{'text'};
	$self->{__PACKAGE__.'.handler_commentline'} = $args{'comment'};
	$self->{__PACKAGE__.'.handler_request'} = $args{'request'};
	$self->{__PACKAGE__.'.buf'} = '';
	$self->{__PACKAGE__.'.text'} = '';
	$self->{__PACKAGE__.'.linenum'} = 0;
	return $self;
}

sub parse
{
	my $self = shift;
	my $buf = \ $self->{__PACKAGE__.'._buf'};
	if (defined $_[0])
	{
		$$buf .= $_[0];
	}
	else
	{
		# signals EOF
		return $self unless length $$buf;
		$$buf .= "\n";
	}

    TOKEN:
	while (1)
	{
		if ($$buf =~ s/^.*\n//o)
		{
			$self->{__PACKAGE__.'.linenum'}++;
			undef $self->{__PACKAGE__.'.comment'};
			local $_ = $&;
			my $suppress = s/^\\\&//o;
			$_ = $self->_process_escapes($_);
			if (!$suppress && s/^([.'])[ \t]*(\S+)((?:[ \t]+.*)?)\n//o)
			{
				my $dot = $1;
				my $req = $2;
				my $args = $3;
				my @args = ();
				push @args, $1 while
					$args =~ s/^\s*"(.*?)(?:"(?!")|$)//o
				     ||	$args =~ s/^\s*(\S.*)$//o;
				my $h = $self->{__PACKAGE__.'.handler_request'};
				if (ref($h) eq 'HASH' && ref($h->{$req}) eq 'CODE')
				{
					&{$h->{$req}}($dot, @args);
				}
				elsif (ref($h) eq 'CODE')
				{
					&$h($dot, $req, @args);
				}
				elsif ($req !~ /\W/o && $self->can($req))
				{
					$self->$req($dot, @args);
				}
				else
				{
					$self->request($dot, $req, @args);
				}
			}
			elsif (!$suppress && s/^([.']).*\n//o)
			{
				local $_ = $self->{__PACKAGE__.'.comment'};
				if (defined)
				{
					my $h = $self->{__PACKAGE__.'.handler_commentline'};
					if (ref($h) eq 'CODE')
					{
						&$h($_);
					}
					else
					{
						$self->comment_line($_);
					}
				}
			}
			elsif (length)
			{
				my $h = $self->{__PACKAGE__.'.handler_text'};
				if (ref($h) eq 'CODE')
				{
					&$h($_);
				}
				else
				{
					$self->text($_);
				}
			}
		}
		else
		{
			# partial line
			last TOKEN;
		}
	}
	return $self;
}

sub eof
{
	shift->parse(undef);
}

sub comment
{
	shift->{__PACKAGE__.'.comment'};
}

sub linenum
{
	shift->{__PACKAGE__.'.linenum'};
}

sub parse_file
{
	my($self, $file) = @_;
	no strict 'refs';  # so that a symbol ref as $file works
	local(*F);
	unless (ref($file) || $file =~ /^\*[\w:]+$/) {
		# Assume $file is a filename
		open(F, $file) || die "Can't open $file: $!";
		$file = \*F;
	}
	my $chunk = '';
	while(read($file, $chunk, 512)) {
		$self->parse($chunk);
	}
	close($file);
	$self->eof;
}

my %escapes =
(
	'\\' => sub { '\\' },
	'&' => sub { '' },
	e => sub { '\\' },
	'\'' => sub { "'" },
	'`' => sub { "`" },
	'"' => sub { shift->{__PACKAGE__.'.comment'} = $1 if s/^(.*)//o; '' },
	'-' => sub { "-" },
	'.' => sub { "." },
	' ' => sub { " " },
	0 => sub { " " },
	'|' => sub { '' },
	'^' => sub { '' },
	'!' => sub { $_ = ''; '' },
	'$' => sub { s/^(\d|\(\d\d|\[\d+\])//o ? '' : '\\$' },
	'%' => sub { '-' },
	'(' => sub { $_ = substr $_, 2; '?' },
	'*' => sub { s/^(.|\(..|\[.+?\])//o ? '' : '\\*' },
	a => sub { '.' },
	b => sub { s/^(.).*?\1//o ? '?' : '\\b' },
	c => sub { '' },
	d => sub { '' },
	D => sub { s/^(.).*?\1//o ? '?' : '\\D' },
	f => sub { s/^(.|\(..|\[.+?\])//o ? '' : '\\f' },
	g => sub { s/^(.|\(..|\[.+?\])//o ? '' : '\\g' },
	h => sub { s/^(.).*?\1//o ? '?' : '\\h' },
	H => sub { s/^(.).*?\1//o ? '?' : '\\H' },
	k => sub { '' },
	l => sub { s/^(.).*?\1//o ? '?' : '\\l' },
	L => sub { s/^(.).*?\1//o ? '?' : '\\L' },
	n => sub { s/^(.|\(..|\[.+?\])//o ? '' : '\\n' },
	o => sub { s/^(.).*?\1//o ? '?' : '\\o' },
	p => sub { '' },
	r => sub { '' },
	s => sub { s/^([+\-]?(\d|\(\d\d|\[\d+\])|\([+\-]?\d\d|\[[+\-]?\d+\])//o ? '' : '\\s' },
	S => sub { s/^(.).*?\1//o ? '' : '\\S' },
	t => sub { "\t" },
	u => sub { '' },
	v => sub { s/^(.).*?\1//o ? '' : '\\v' },
	w => sub { s/^(.).*?\1//o ? '?' : '\\w' },
	x => sub { s/^(.).*?\1//o ? '' : '\\x' },
	z => sub { s/^(.)//o ? '' : '\\z' },
	'{' => sub { '' },
	'}' => sub { '' },
);

sub _process_escapes
{
	my $self = shift;
	local $_ = shift;
	my $r = '';
	while (s/^(.*?)\\(.)//so)
	{
		$r .= $1;
		$r .= &{$escapes{$2} || sub { $_[1] }}($self, $2);
	}
	return $r.$_;
}

sub _comment
{
	my $self = shift;
	my $com = \$self->{__PACKAGE__.'.comment'};
	if (@_)
	{
		$$com .= $_[0];
	}
	else
	{
		$self->comment($$com) if length $$com;
		$$com = '';
	}
}

# Override these.

sub text
{
	# my ($self, $text) = @_;
}

sub comment_line
{
	# my ($self, $comment) = @_;
}

sub request
{
	# my ($self, $dot, $req, @args) = @_;
}

1;
