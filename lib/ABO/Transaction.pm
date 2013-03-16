package ABO::Transaction;
use feature 'unicode_strings';

use ABO::Base;
@ISA = qw(
	ABO::Base
);

use overload
	'""' => "as_string",
	'bool' => sub { 1; },
	;

use Carp qw(confess);

my $unique_id_counter = 1;

sub init
{
	my ($self, %a) = @_;
	$self->{'unique_id'} = $unique_id_counter++;
	$self->{'entries'} = [];
	local $x;
	if (defined $a{'-serialized'})
	{
		$x = $self->scope_error_func(sub {
			$self->_error("invalid ".__PACKAGE__." serialization: ", @_);
		});
		my @m = split /\001/, $a{'-serialized'}, -1;
		if (@m < 6)
		{
			$self->error("missing fields");
			return undef;
		}
		$self->{'date'} = $self->make_date(shift @m) or return undef;
		$self->{'cdate'} = $self->make_date(shift @m) or return undef;
		@{$self}{'who', 'what'} = splice @m, 0, 2;
                utf8::upgrade($self->{'who'});
                utf8::upgrade($self->{'what'});
		for my $se (@m)
		{
			my $e = $self->make(ABO::Entry,
					-transaction => $self,
					-serialized => $se,
				) or return undef;
			push @{$self->{'entries'}}, $e;
		}
	}
	else
	{
		my ($date, $cdate, $ents);
		if (defined $a{'-string'})
		{
			my $s = $a{'-string'};
			$x = $self->scope_error_func(sub {
				$self->_error("invalid ".__PACKAGE__." string `$s': ", @_);
			});
			my @m = ($s =~ /^([^\s,]+)(?:,(\S+))?\s+(\S*)\s+(.*)$/o);
			if (@m != 4)
			{
				$self->error("missing fields");
				return undef;
			}
			($date, $cdate) = @m[0, 1];
			$ents = [ map { s/;;/;/og; $_ }
					split /(?<!;);(?!;)/, $m[2]
				];
			if ($m[3] =~ /^(.*?)\s*;\s*(.*)$/o)
			{
				@{$self}{'who', 'what'} = ($1, $2);
			}
			else
			{
				@{$self}{'who', 'what'} = ($m[3], '');
			}
		}
		else
		{
			$x = $self->scope_error_func(sub {
				$self->_error(@_);
			});
			confess "undefined -date arg" unless defined $a{'-date'};
			confess "undefined -who arg" unless defined $a{'-who'};
			confess "undefined -what arg" unless defined $a{'-what'};
			($date, $cdate, $ents) = @a{'-date', '-cdate', '-entries'};
			@{$self}{'who', 'what'} = @a{'-who', '-what'};
		}

		confess "entries undefined" unless defined $ents;

		$date = $self->make_date($date);
		if (defined $cdate)
		{
			$cdate = $self->make_date($cdate, $date);
		}
		else
		{
			$cdate = $date;
		}
		$self->{'date'} = $date;
		$self->{'cdate'} = $cdate;

		confess "entries not array ref" unless ref($ents) eq 'ARRAY';
		confess "no entries" unless @$ents;
		for my $ent (@$ents)
		{
			my $e;
			if (UNIVERSAL::isa($ent, ABO::Entry))
			{
				$e = $self->make(ABO::Entry,
						-transaction => $self,
						-entry => $ent,
					);
			}
			elsif (ref($ent) eq 'HASH')
			{
				$e = $self->make(ABO::Entry,
						-transaction => $self,
						-dbcr => $ent->{dbcr},
						-account => $ent->{account},
						-amount => $ent->{amount},
						-detail => $ent->{detail},
					);
			}
			else
			{
				$e = $self->make(ABO::Entry,
						-transaction => $self,
						-string => $ent,
					);
			}
			return undef unless $e;
			push @{$self->{'entries'}}, $e;
		}
	}

	# Check that the entries balance.
	my $bal = $self->make_money(0);
	for my $e ($self->entries)
	{
		$bal += $e->dbcr eq 'cr' ? $e->amount : -$e->amount;
	}
	$self->error("entries unbalanced") if $bal;

        @{$self->{'entries'}} = sort {
                   $a->amount_signed <=> $b->amount_signed
                || $a->account->name cmp $b->account->name
                || $a->detail cmp $b->detail
            } @{$self->{'entries'}};

	return undef if $self->{'_error'};
	$self->_nucleus->validate_transaction($self) or return undef;

	return $self;
}

sub _error
{
	my $self = shift;
	$self->{'_error'} = 1;
	$self->error(@_);
}

sub unique_id { $_[0]->{'unique_id'}; }
sub date { $_[0]->{'date'}; }
sub cdate { $_[0]->{'cdate'}; }
sub who { $_[0]->_expand($_[0]->{'who'}); }
sub what { $_[0]->_expand($_[0]->{'what'}); }

sub amount
{
	my $self = shift;
        my $amount = $self->make_money(0);
	for my $e ($self->entries) {
		$amount += $e->amount if $e->dbcr eq 'cr';
	}
        return $amount;
}

sub desc
{
	my $self = shift;
	return join '; ', grep { length } ($self->who, $self->what);
}

sub entries
{
	my $self = shift;
	return @{$self->{'entries'}};
}

sub serialize
{
	my $self = shift;
        my $who = $self->{'who'};
        my $what = $self->{'what'};
        utf8::downgrade($who);
        utf8::downgrade($what);
	return join "\001",
		$self->{'date'}->serialize,
		$self->{'cdate'}->serialize,
		$who,
		$what,
		map { $_->serialize } $self->entries;
}

sub as_string
{
	my $self = shift;
	local $^W = undef;
	return	$self->date.
		($self->date != $self->cdate ? ','.$self->cdate : '').' '.
		join(';',	map { s/;/;;/og; $_ }
				map { $_->as_string }
				$self->entries
			).' '.
		$self->desc;
}

sub _expand
{
	my $self = shift;
	local $_ = shift;
	s/%{(date|due)((?:[+\-]\d+)?)}/ eval("\$self->$1 $2")->format('%-d-%b-%Y') /eog;
	return $_;
}

1;
