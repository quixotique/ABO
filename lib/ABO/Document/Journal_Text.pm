package ABO::Document::Journal_Text;

use ABO::Entry;
use ABO::Document::Parser;
use ABO::Document::Journal::Parser;
@ISA = qw(
	ABO::Document::Parser
	ABO::Document::Journal::Parser
);

use ABO::Utils qw(pick system_io);
use Carp qw(confess);

sub _parse
{
	my $self = shift;
	$self->_parse_journal(@_) or return undef;
	return $self;
}

sub doctype { 'journal' }
sub ref { $_[0]->{'ref'} }

sub probe
{
	shift if @_ && UNIVERSAL::isa($_[0], __PACKAGE__);
	local $_ = shift;
	return scalar m/^(#.*\n)*%journal\b/o;
}

sub _filter
{
	my ($self, $body) = @_;
	return $body unless $body =~ m/^(?:[#%].*\n)*%filter\s+(.*)/o;
	my $filter_cmd = $1;
	my $fbody;
	my $ferr;
	$self->blah("invoke filter command: $filter_cmd");
	my $stat = system_io($filter_cmd, $body, \$fbody, \$ferr);
	return $fbody if $stat == 0 and length($ferr) == 0;
	$self->error("filter command `$filter_cmd' terminated with status $stat") if $stat;
	$self->error("filter command `$filter_cmd' terminated with error message:\n$ferr") if length $ferr;
	return undef;
}

sub _parse_journal
{
	my ($self, $body) = @_;

	$self->{'parser'} = ABO::Document::Journal::Parser->new(
		error => sub {
				$self->_error("line ", $self->linenum, ": ",
					@_ ? @_ : "malformed line"
				)
			},
		entry => sub { $self->_h_entry(@_) },
		directive => {
			ref => sub { $self->_h_ref(@_) },
		},
		comment => sub { $self->_h_comment(@_) },
	);

	$body = $self->_filter($body) or return undef;
	$self->_parser->parse($body)->eof or return undef;

	my @trans = $self->unsorted_transactions;
	$self->_error("missing %ref field") unless defined $self->ref;
	$self->_error("no transactions") unless @trans;
	return undef if $self->{'error'};

	my ($first, $last);
	for my $t (@trans)
	{
		my $date = $t->date;
		$first = $date unless
			defined($first) && $first < $date;
		$last = $date unless
			defined($last) && $last > $date;
	}
	$self->_set_attribute('Number of transactions', scalar @trans);
	if ($n)
	{
		$self->_set_attribute('Earliest transaction', $first);
		$self->_set_attribute('Latest transaction', $last);
	}

	return $self;
}

sub _h_ref
{
	my ($self, $val) = @_;
	$self->{'ref'} = $val;
}

sub _h_comment
{
	my ($self, $text) = @_;
	$self->_parser->linenum($1 - 1) if $text =~ m/^line (\d+)/o;
}

sub _h_entry
{
	my ($self, %ent) = @_;
	my $default = $self->{'default'};
	$self->{'gotkeys'} = {};

	my $err = 0;
	my $due;
	my $type = $self->getent('type');
	my $date = $self->getent('date');
	my $what = $self->getent('what');
	my $who = $self->getent('who');

	$err = 1 unless $self->assert_is_one($type);
	$err = 1 unless $self->assert_is_one($date);
	$err = 1 unless $self->assert_is_one($what);
	$err = 1 unless $self->assert_is_optone($who);
	return if $err;

	my @en = ();
	if ($type eq 'invoice' || $type eq 'bill')
	{
		my $acc_dbcr = $type eq 'invoice' ? 'db' : 'cr';
		my $item_dbcr = $type eq 'invoice' ? 'cr' : 'db';
		$due = $self->getent('due');
		my $acc = $self->getent('acc');
		my $amt = $self->getent('amt');
		my $gst = $self->getent('gst');
		my @items = $self->getent_multi('item');
		$err = 1 unless $self->assert_is_one($acc);
		$err = 1 unless $self->assert_is_optone($due);
		$err = 1 unless $self->assert_is_optone($amt);
		$err = 1 unless $self->assert_is_optone($gst);
		return if $err;
		my ($det, $totamt);
		if ($amt)
		{
			$totamt = "$amt";
			$det = $totamt =~ s/(\S)\s+(.*?)\s*$/$1/o ? $2 : '';
			$totamt = $self->make_money($totamt);
		}
		my $tot = $self->make_money(0);
		if ($gst)
		{
			my $gstac = $type eq 'invoice'
				? $self->_config->var('invoice_gst_credit')
				: $self->_config->var('bill_gst_debit');
			my $gstamt = $self->make_money("$gst");
			my $dbcr = $item_dbcr;
			if (1) # if ($gstamt > 0)
			{
				$tot += $gstamt;
				if (	defined $totamt
				    &&	($totamt < 0 ? $tot < $totamt : $tot > $totamt)
				)
				{
					$self->_error_val("invalid", $gst, "total exceeded");
				}
				else
				{
					push @en, _entry($item_dbcr, $gstac, $gstamt, 'GST');
				}
			}
			else
			{
				$self->_error_val("invalid", $gst);
				return;
			}
		}
	ITEM:	for my $item (@items)
		{
			local $_ = "$item";
			my ($iac, $iamt);
			if (!s/^\s*(\S+)//o)
			{
				$self->_error_val("malformed", $item,
					"missing account name"
				);
				$err = 1;
				next ITEM;
			}
			$iac = $1;
			if (s/^\s*(-?\d*\.\d{1,2}|-?\d+)(?=\s|$)//o)
			{
				$iamt = $1;
				$tot += $iamt;
			}
			elsif (defined $totamt && $tot != $totamt)
			{
				$iamt = $totamt - $tot;
				$tot = $totamt;
			}
			else
			{
				$self->_error_val("incomplete", $item,
					"missing amount"
				);
				$err = 1;
				next ITEM;
			}
			s/^\s+//o;
			s/\s+$//o;
			push @en, _entry($item_dbcr, $iac, $iamt, $_);
		}
		return if $err;
		if (defined $totamt && $tot != $totamt)
		{
			if (@items == 0)
			{
				my $dbcrdef = $type eq 'invoice'
					? $self->_config->var('invoice_item_credit_default')
					: $self->_config->var('bill_item_debit_default');
				if (defined $dbcrdef)
				{
					push @en, _entry($item_dbcr, $dbcrdef, $totamt - $tot);
					$tot = $totamt;
				}
				else
				{
					$err = 1;
				}
			}
			else
			{
				$self->_error_trans("missing `item'");
				$err = 1;
			}
		}
		push @en, _entry($acc_dbcr, $acc, $tot, $det) if $tot;
	}
	elsif ($type eq 'remittance' || $type eq 'receipt')
	{
		my $acc_dbcr = $type eq 'remittance' ? 'db' : 'cr';
		my $bank_dbcr = $type eq 'remittance' ? 'cr' : 'db';
		my $acc = $self->getent('acc');
		my $amt = $self->getent('amt');
		my $bank = $self->getent('bank');
		$err = 1 unless $self->assert_is_one($acc);
		$err = 1 unless $self->assert_is_one($amt);
		$err = 1 unless $self->assert_is_one($bank);
		return if $err;
		local $_ = "$acc";
		if (s/^\s*(\S+)//o)
		{
			my $ac = $1;
			s/^\s+//o;
			s/\s+$//o;
			push @en, {
					dbcr => $acc_dbcr,
					account => $ac,
					amount => "$amt",
					detail => $_,
				};
		}
		else
		{
			$self->_error_val("malformed", $acc,
				"missing account name"
			);
			$err = 1;
		}
		$_ = "$bank";
		if (s/^\s*(\S+)//o)
		{
			my $ac = $1;
			s/^\s+//o;
			s/\s+$//o;
			push @en, {
					dbcr => $bank_dbcr,
					account => $ac,
					amount => "$amt",
					detail => $_,
				};
		}
		else
		{
			$self->_error_val("malformed", $bank,
				"missing account name"
			);
			$err = 1;
		}
	}
	elsif ($type eq 'transaction')
	{
		my $amt = $self->getent('amt');
		my $dbs = $self->getent('db');
		my $crs = $self->getent('cr');
		$err = 1 unless $self->assert_is_optone($amt);
		$err = 1 unless $self->assert_is_multi($dbs);
		$err = 1 unless $self->assert_is_multi($crs);
		return if $err;
		my @dbcr = sort { $a->linenum <=> $b->linenum }
			map { $_ > 1 ? $_->values : $_ }
			$dbs, $crs;
		my $totamt = $amt ? $self->make_money("$amt") : undef;
		my $totdb = $self->make_money(0);
		my $totcr = $self->make_money(0);
		my (@dbcrna, $dbu, $cru);
	DBCR:	for my $e (@dbcr)
		{
			local $_ = "$e";
			my $dbcr = $e->key;
			my ($eac, $eamt, $det);
			if (!s/^\s*(\S+)//o)
			{
				$self->_error_val("malformed", $e,
					"missing account name"
				);
				$err = 1;
				next DBCR;
			}
			$eac = $1;
			$eamt = $1 if s/^\s*(-?\d*\.\d{1,2}|-?\d+)(?=\s|$)//o;
			s/^\s+//o;
			s/\s+$//o;
			$det = $_;
			if (defined $eamt)
			{
				if ($eamt < 0)
				{
					$dbcr = ABO::Entry::dbcr_invert($dbcr);
					$dbcr = -$dbcr;
				}
				if ($dbcr eq 'db')
				{
					$totdb += $eamt;
					if (defined $totamt && $totdb > $totamt)
					{
						$self->_error_val("invalid", $e,
							"debits exceed total"
						);
						$err = 1;
						next DBCR;
					}
				}
				elsif ($dbcr eq 'cr')
				{
					$totcr += $eamt;
					if (defined $totamt && $totcr > $totamt)
					{
						$self->_error_val("invalid", $e,
							"credits exceed total"
						);
						$err = 1;
						next DBCR;
					}
				}
				push @en, _entry($dbcr, $eac, $eamt, $det)
					if $eamt;
			}
			else
			{
				push @dbcrna, [ $e, $dbcr, $eac, $det ];
			}
		}

		for my $na (@dbcrna)
		{
			my ($e, $dbcr, $eac, $det) = @$na;
			my $eamt;
			if ($dbcr eq 'db' && defined $totamt && $totdb < $totamt)
			{
				$eamt = $totamt - $totdb;
				$totdb = $totamt;
			}
			elsif ($dbcr eq 'db' && !defined $dbu)
			{
				$dbu = [ $e, $eac, $det ];
			}
			elsif ($dbcr eq 'cr' && defined $totamt && $totcr < $totamt)
			{
				$eamt = $totamt - $totcr;
				$totcr = $totamt;
			}
			elsif ($dbcr eq 'cr' && !defined $cru)
			{
				$cru = [ $e, $eac, $det ];
			}
			else
			{
				$self->_error_val("incomplete", $e,
					"missing amount"
				);
				$err = 1;
			}
			push @en, _entry($dbcr, $eac, $eamt, $det) if $eamt;
		}
		return if $err;
		if ($dbu && $cru)
		{
			if (defined $totamt)
			{
				for my $e (sort { $a->linenum <=> $b->linenum} $dbu->[0], $cru->[0])
				{
					$self->_error_val("incomplete", $e,
						"missing value"
					);
				}
			}
			else
			{
				$self->_error_val("missing", $amt);
			}
			$err = 1;
		}
		elsif ($dbu)
		{
			if ($totdb < $totcr)
			{
				push @en, _entry('db', $dbu->[1], $totcr - $totdb, $dbu->[2]);
				$totdb = $totcr;
			}
			else
			{
				$self->_error_val("incomplete", $dbu->[0],
					"missing amount"
				);
				$err = 1;
			}
		}
		elsif ($cru)
		{
			if ($totcr < $totdb)
			{
				push @en, _entry('cr', $cru->[1], $totdb - $totcr, $cru->[2]);
				$totcr = $totdb;
			}
			else
			{
				$self->_error_val("incomplete", $cru->[0],
					"missing amount"
				);
				$err = 1;
			}
		}
		return if $err;
		if ($totdb > $totcr)
		{
			$self->_error_trans("debits exceed credits");
			$err = 1;
		}
		elsif ($totcr > $totdb)
		{
			$self->_error_trans("credits exceed debits");
			$err = 1;
		}
	}
	else
	{
		$self->_error_val("invalid", $type, "\"$type\"");
		return;
	}

	for my $e (	sort { $a->linenum <=> $b->linenum }
			map { $self->_parser->getent($_) }
			grep { !$self->{'gotkeys'}->{$_} }
			$self->_parser->getkeys
	)
	{
		$self->_error_val("spurious", $e);
		$err = 1;
	}

	return if $err;

	confess "no entries" unless @en;
	my $tempnuc = $self->_nucleus->fork;
	$tempnuc->fork_error_reporter->push_error_func(sub {
		$self->_error_trans(@_);
	});
	my $t = $tempnuc->make(ABO::Transaction,
		-date => "$date",
		-cdate => $due ? "$due" : undef,
		-who => $who ? "$who" : '',
		-what => $what,
		-entries => \@en,
	) or return;

	push @{$self->{'transactions'}}, $t;
}

sub _parser { $_[0]->{'parser'} }

sub _entry
{
	my ($dbcr, $acc, $amt, $det) = @_;
	return {
		dbcr => $amt < 0 ? ABO::Entry::dbcr_invert($dbcr) : $dbcr,
		account => $acc,
		amount => abs $amt,
		detail => defined $det ? $det : '',
	}
}

sub linenum { $_[0]->_parser->linenum }

sub getent
{
	my ($self, $key) = @_;
	$self->{'gotkeys'}->{$key} = 1;
	return $self->_parser->getent($key);
}

sub getent_multi
{
	my ($self, $key) = @_;
	my $e = $self->getent($key);
	return $e->values if $e > 1;
	return ($e) if $e == 1;
	return ();
}

sub assert_is_optone
{
	my ($self, $ent) = @_;
	return 1 if $ent <= 1;
	$self->_error_val("more than one", $ent);
	return undef;
}

sub assert_is_one
{
	my ($self, $ent) = @_;
	return 1 if $ent == 1;
	$self->_error_val("more than one", $ent) if $ent > 1;
	$self->_error_val("missing", $ent) if $ent < 1;
	return undef;
}

sub assert_is_multi
{
	my ($self, $ent) = @_;
	return 1 if $ent >= 1;
	$self->_error_val("missing", $ent);
	return undef;
}

sub _error
{
	my $self = shift;
	$self->{'error'} = 1;
	$self->error(@_);
}

sub _error_val
{
	my ($self, $msg, $val) = splice @_, 0, 3;
	my $key = $val->key;
	if ($val->is_default)
	{
		$self->_error_trans($msg, " default `$key'",
			" at "._line_str($val),
			@_ ? ' - ' : '', @_
		);
	}
	elsif ($val > 0)
	{
		$self->_error(_line_str($val), ": ", $msg, " `$key'", @_ ? ' - ' : '', @_);
	}
	else
	{
		$self->_error_trans($msg, " `$key'", @_ ? ' - ' : '', @_);
	}
}

sub _line_str
{
	my $val = shift;
	my @ln = $val->can('linenums') ? $val->linenums : ($val->linenum);
	return (@ln == 1 ? 'line ' : 'lines ').join(', ', @ln);
}

sub _error_trans
{
	my $self = shift;
	$self->_error("transaction at line ",
		$self->linenum, ": ", @_
	);
}

1;
