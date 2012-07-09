package ABO::Document::Invoice_Common;

use ABO::Transaction;
use ABO::Utils qw(empty);

use Carp qw(confess);

sub _parse
{
	my $self = shift;
	$self->{'items'} = [];
	$self->_parse_invoice(@_) or return undef;
	$self->_make_invoice_transactions or return undef;
	return $self;
}

sub doctype { 'invoice' }
sub ref { shift->{'ref'} }
sub _description { 'Invoice '.$_[0]->ref }
sub _items { @{shift()->{'items'}} }

sub _make_invoice_transactions
{
	my $self = shift;
	my %ia = ();
	my %in = ();
	my %co = ();
	for my $item ($self->_items)
	{
		my ($ac, $amt, $com, $iline) = @$item;
		return undef unless defined $ac;
		if (length $ac)
		{
			$in{$ac} = [] unless defined $in{$ac};
		}
		else
		{
			$ac = $self->_config->var('invoice_item_credit_default');
			return undef unless defined $ac;
			$self->_config->var_error_invalid(
				'invoice_item_credit_default',
				"invalid account `$ac'"
			), return undef
				unless $self->_nucleus->account_list->
				get_account_byname($ac);
		}
		push @{$in{$ac}}, $iline;
		$co{$ac} = '' unless defined $co{$ac};
		$co{$ac} .= ' '.$com if !empty $com;
		$ia{$ac} = $self->make_money(0) unless defined $ia{$ac};
		$ia{$ac} += $amt;
	}

	my @en = ();
	my $db = $self->make_money(0);
	for my $a (keys %ia)
	{
		next unless $ia{$a};
		$db += $ia{$a};
		push @en, {
				dbcr => 'cr',
				account => $a,
				amount => $ia{$a},
				detail => $co{$a},
			};
	}
	push @en, {
			dbcr => 'db',
			account => $self->{'account'},
			amount => $db,
			detail => '',
		};

	my $tempnuc = $self->_nucleus->fork;
#	my $prefix = "line".(@{$in{$a}} == 1 ? '' : 's').
#			" ".join(', ', @{$in{$a}}).": ";
#	$tempnuc->fork_error_reporter->push_error_func(sub {
#		$self->error($prefix, @_);
#	});
	my $t = $tempnuc->make(ABO::Transaction,
			-date => $self->{'date'},
			-cdate => $self->{'due'},
			-who => $self->{'customer'},
			-what => $self->_description,
			-entries => \@en,
		)
		or return undef;
	push @{$self->{'transactions'}}, $t;
	return $self;
}

sub _map_account
{
	my $self = shift;
	my $ac = shift;
	my $map = $self->{'item_map'};
	if (!defined $map)
	{
		$map = $self->_config->var('invoice_item_credit_map');
		if (defined $map)
		{
			$map =~ s/[^\w*]/\\$&/og;
			$map =~ s/\*/\$\&/og;
			$self->{'item_map'} = $map;
		}
		else
		{
			$map = $self->{'item_map'} = '';
		}
	}
	return undef unless length $map;
	eval "\$ac =~ s/.*/$map/";
	return $ac;
}

1;
