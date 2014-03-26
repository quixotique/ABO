package ABO::Document::Journal::Parser::Value;
use feature 'unicode_strings';
use overload
	'""' => \&value,
	'0+' => sub { 1 },
	'bool' => sub { 1 },
	'<=>' => \&ncmp,
	'cmp' => \&cmp,
	fallback => undef,
	;

sub new
{
	my $class = shift;
	bless {
		value => $_[0],
		key => $_[1],
		linenum => $_[2],
		is_default => $_[3],
	}, $class;
}

sub ncmp
{
	my ($self, $n, $rev) = @_;
	my $r = 1 <=> $n + 0;
	return $rev ? -$r : $r;
}

sub cmp
{
	my ($self, $n, $rev) = @_;
	my $r = $self->value cmp "$n";
	return $rev ? -$r : $r;
}

sub value { my $s = $_[0]->{value}; "$s" }
sub key { $_[0]->{key} }
sub linenum { $_[0]->{linenum} }
sub is_default { $_[0]->{is_default} }

package ABO::Document::Journal::Parser::ValueList;

use overload
	'""' => \&value,
	'0+' => \&count,
	'bool' => sub { $_[0]->count != 0 },
	'<=>' => \&ncmp,
	'cmp' => \&cmp,
	fallback => undef,
	;

sub new
{
	my $class = shift;
	bless { key => $_[0], values => [] }, $class;
}

sub push
{
	my $self = shift;
	push @{$self->{values}}, ABO::Document::Journal::Parser::Value->new(@_);
}

sub ncmp
{
	my ($self, $n, $rev) = @_;
	my $r = $self->count <=> $n + 0;
	return $rev ? -$r : $r;
}

sub cmp
{
	my ($self, $n, $rev) = @_;
	my $r = $self->value cmp "$n";
	return $rev ? -$r : $r;
}

sub key { $_[0]->{key} }
sub values { @{$_[0]->{values}} }
sub linenums { map { $_->linenum } $_[0]->values }
sub count { scalar $_[0]->values }

sub value
{
	my $self = shift;
	my $values = $self->{values};
	@$values ? $values->[0]->value : undef;
}

sub linenum
{
	my $self = shift;
	my $values = $self->{values};
	@$values ? $values->[0]->linenum : undef;
}

sub is_default
{
	my $self = shift;
	my $values = $self->{values};
	@$values ? $values->[0]->is_default : undef;
}

package ABO::Document::Journal::Parser;

# Author: Andrew Bettison <andrewb@zip.com.au>

use strict;

use vars qw($VERSION);
$VERSION = "1.00";


sub new
{
	my $class = shift;
	my $self = bless {}, ref($class) || $class;
	my %args = @_;
	$self->{__PACKAGE__.'.handler_entry'} = $args{'entry'};
	$self->{__PACKAGE__.'.handler_commentline'} = $args{'comment'};
	$self->{__PACKAGE__.'.handler_directive'} = $args{'directive'};
	$self->{__PACKAGE__.'.handler_error'} = $args{'error'};
	$self->{__PACKAGE__.'.buf'} = '';
	$self->{__PACKAGE__.'.linenum'} = 0;
	$self->{__PACKAGE__.'.default'} = {};
	undef $self->{__PACKAGE__.'.entry'};
	undef $self->{__PACKAGE__.'.entry_linenum'};
	return $self;
}

sub parse
{
	my $self = shift;
	my $str = shift;
	my $buf = \ $self->{__PACKAGE__.'._buf'};
	my $ent = \ $self->{__PACKAGE__.'.entry'};

	$$buf .= $str if defined $str;

    LINE:
	while (1)
	{
		if ($$buf =~ s/^.*\n//o)
		{
			$self->{__PACKAGE__.'.linenum'}++;
			undef $self->{__PACKAGE__.'.comment'};
			local $_ = $&;
			chop;
			if (/^%\s*(\S+)\s*(.*)$/o)
			{
				my $dir = $1;
				my $dirm = "dir_$dir";
				my $arg = $2;
				my $h = $self->{__PACKAGE__.'.handler_directive'};
				if (ref($h) eq 'HASH' && ref($h->{$dir}) eq 'CODE')
				{
					&{$h->{$dir}}($arg);
				}
				elsif (ref($h) eq 'CODE')
				{
					&$h($dir, $arg);
				}
				elsif ($dir !~ /\W/o && $self->can($dirm))
				{
					$self->$dirm($arg);
				}
				else
				{
					$self->directive($dir, $arg);
				}
			}
			elsif (/^#(.*)$/o)
			{
				local $_ = $1;
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
			elsif (/^(\w+)\t(.*)$/o)
			{
				my ($key, $val) = ($1, $2);
				if (!defined $$ent)
				{
					$self->{__PACKAGE__.'.entry_linenum'} = $self->linenum;
					$$ent = {};
				}
				$$ent->{$key} = ABO::Document::Journal::Parser::ValueList->new($key)
					unless $$ent->{$key};
				$$ent->{$key}->push($val, $key, $self->linenum);
			}
			elsif (length)
			{
				$self->_error();
			}
			else
			{
				$self->_entry;
			}
		}
		else
		{
			# partial line
			last LINE;
		}
	}
	if (!defined $str)
	{
		# Signals EOF.
		$self->_entry;
	}
	return $self;
}

sub eof
{
	$_[0]->parse(undef);
}

sub _entry
{
	my $self = shift;
	my $ent = \ $self->{__PACKAGE__.'.entry'};
	return unless defined $$ent;
	local $self->{__PACKAGE__.'.linenum'} = $self->{__PACKAGE__.'.entry_linenum'};
	my $h = $self->{__PACKAGE__.'.handler_entry'};
	if (ref($h) eq 'CODE')
	{
		&$h(%$$ent);
	}
	else
	{
		$self->entry(%$$ent);
	}
	undef $$ent;
}

sub linenum
{
	my $self = shift;
	$self->{__PACKAGE__.'.linenum'} = shift if @_;
	$self->{__PACKAGE__.'.linenum'};
}

sub getkeys
{
	my $self = shift;
	keys %{$self->{__PACKAGE__.'.entry'}};
}

sub getent
{
	my ($self, $key) = @_;
	my $e = $self->{__PACKAGE__.'.entry'}->{$key};
	$e = $self->{__PACKAGE__.'.default'}->{$key} unless defined $e;
	return ABO::Document::Journal::Parser::ValueList->new($key)
		if !defined $e;
	return $e;
}

sub parse_file
{
	my($self, $file) = @_;
	no strict 'refs';  # so that a symbol ref as $file works
	local(*F);
	unless (ref($file) || $file =~ /^\*[\w:]+$/) {
		# Assume $file is a filename
		open(F, $file) || die "Can't open $file: $!";
                binmode(F, ':encoding(UTF-8)') || die "Can't set utf-8 encoding of $file: $!";
		$file = \*F;
	}
	my $chunk = '';
	while(read($file, $chunk, 512)) {
		$self->parse($chunk);
	}
	close($file);
	$self->eof;
}

sub _error
{
	my $self = shift;
	my $h = $self->{__PACKAGE__.'.handler_error'};
	if (ref($h) eq 'CODE')
	{
		&$h(@_);
	}
	else
	{
		$self->error(@_);
	}
}

# Override these.

sub dir_default
{
	my ($self, $arg) = @_;
	my $def = \ $self->{__PACKAGE__.'.default'};
	if ($arg =~ /^(\w+)\s+(.*)$/)
	{
		my ($key, $val) = ($1, $2);
                $$def->{$key} = ABO::Document::Journal::Parser::Value->new($val, $key, $self->linenum, 1);
        }
	elsif ($arg =~ /^(\w+)$/)
        {
		my $key = $1;
                delete $$def->{$key};
	}
	else
	{
		$self->_error("invalid %default line");
	}
}

sub entry
{
	# my ($self, %ent) = @_;
}

sub comment_line
{
	# my ($self, $comment) = @_;
}

sub directive
{
	# my ($self, $dir, $arg) = @_;
}

sub error
{
	# my ($self, %ent) = @_;
}

1;
