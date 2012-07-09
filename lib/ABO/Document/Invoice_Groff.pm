package ABO::Document::Invoice_Groff;
use feature 'unicode_strings';

use ABO::Document::Invoice_Common;
use ABO::Document::Parser;
use ABO::Document::Common_Groff;
@ISA = qw(
	ABO::Document::Invoice_Common
	ABO::Document::Parser
	ABO::Document::Common_Groff
);
use Groff::Parser;

sub probe
{
	shift if @_ && UNIVERSAL::isa($_[0], __PACKAGE__);
	local $_ = shift;
	return scalar m/^([.']\S.*\n)*[.'](TaxInvoice|Invoice)(\s|$)/o;
}

sub _description
{
	my $self = shift;
	$self->{'tax'} ? 'Tax invoice '.$self->ref : $self->SUPER::_description;
}

sub _parse_invoice
{
	my ($self, $body) = @_;

	$self->{'total-gst'} = $self->make_money(0);

	$self->{'parser'} = Groff::Parser->new(
		text => sub { $self->_h_text(@_) },
		request => {
			Invoice => sub { $self->_h_ident(0) },
			TaxInvoice => sub { $self->_h_ident(1) },
			Ref => sub { $self->_h_ref(@_) },
			Date => sub { $self->_h_date(@_) },
			Account => sub { $self->_h_account(@_) },
			Customer => sub { $self->_h_customer(@_) },
			Item => sub { $self->_h_item(@_) },
			Price => sub { $self->_h_price(@_) },
			PriceGST => sub { $self->_h_pricegst(@_) },
			GST => sub { $self->_h_gst(@_) },
			Total => sub { $self->_h_total(@_) },
			TotalGST => sub { $self->_h_totalgst(@_) },
			Due => sub { $self->_h_due(@_) },
			Terms => sub { $self->_h_terms(@_) },
		}
	);

	{
		local $x = $self->scope_error_func(sub {
			$self->_syntax(@_);
		});
		$self->_parser->parse($body)->eof or return undef;
	}

	$self->_check_has_ref;
	$self->_check_has_date;
	$self->_check_has_account;
	$self->_check_has_customer;
	$self->_check_has_total;

	$self->_error("missing at least one .Item") unless $self->_items;
	$self->_error(
		"line ", $self->{'iline'}, ": .Item without matching .Price"
	) if defined $self->{'iline'};
	$self->_error(
		"line ", $self->{'acline'},
		": invalid account `", $self->{'account'}, "'"
	) if	defined($self->{'account'}) &&
		!defined $self->_nucleus->account_list->
			get_account_byname($self->{'account'});
	
	my $total = $self->{'total'};
	my $itot = $self->make_money(0);
	my $i;
	for $i ($self->_items) {
		$itot += $i->[1];
	}

	if ($self->{'tax'})
	{
		$self->_check_has_gst;
		my $gstac = $self->_config->var('invoice_gst_credit');
		my $gst = $self->{'gst'};
		my $totalgst = $self->{'totalgst'};
		my $gtot = $self->{'total-gst'};
		if (defined $gst)
		{
			$self->_error("line ", $self->{'gstline'}, ": gst `$gst' is not equal to the sum of item gsts `$gtot'")
				unless $gtot == $gst;
		}
		else {
			$gst = $gtot;
		}
		push @{$self->{'items'}}, [$gstac, $gst, "GST", $self->{'gstline'}] if $gst != 0;
		if (defined $totalgst) {
			if (defined $total) {
				$self->_error("line ", $self->{'totline'}, ": total-with-gst `$totalgst' is not equal to total `$total' plus gst `$gst'")
					unless $totalgst == $total + $gst;
			}
			else {
				$total = $totalgst - $gst;
			}
		}
	}
	else
	{
		$self->_error("line ", $self->{'gstline'}, ": .GST only allowed in tax invoices") if defined $self->{'gst'};
		$self->_error("line ", $self->{'gstline'}, ": .TotalGST only allowed in tax invoices") if defined $self->{'totalgst'};
	}

	if (defined $total)
	{
		$self->_error("line ", $self->{'totline'}, ": total `", $self->{'total'}, "' is not equal to sum of items `$itot'")
			if $itot != $self->{'total'};
	}

	if (defined $self->{'terms'})
	{
		$self->{'due'} = $self->{'date'} + $self->{'terms'} if
			$self->{'date'};
	}
	elsif (!defined $self->{'due'})
	{
		$self->error("Warning: missing .Due or .Terms -- assuming due immediately");
		$self->{'due'} = $self->{'date'};
	}

	return undef if $self->{'error'};

	$self->_set_attribute('Date', $self->{'date'});
	$self->_set_attribute('Due', $self->{'due'});
	$self->_set_attribute('Account', $self->{'account'});
	$self->_set_attribute('Customer', $self->{'customer'});
	$self->_set_attribute('Total', $self->{'total'});
	$self->_set_attribute('GST', $self->{'gst'}) if defined $self->{'gst'};

	return $self;
}

sub _h_ident
{
	my ($self, $flag) = @_;
	$self->error("only one .Invoice or .TaxInvoice allowed"), return
		if defined $self->{'tax'};
	$self->{'tax'} = $flag;
}

sub _h_item
{
	my ($self, $dot, @args) = @_;
	$self->_enditem if defined $self->{'iline'};
	$self->{'iline'} = $self->_parser->linenum;
	$self->{'iaccount'} = @args ? $args[0] : '';
}

sub _h_price
{
	my ($self, $dot, @args) = @_;
	$self->error(".Price without prior .Item"), return
		unless defined $self->{'iline'};
	$self->error("only one .Price allowed"), return
		if defined $self->{'price'};
	$self->error(".Price missing argument"), return
		unless @args && length $args[0];
	my $n = $self->make_money($args[0]);
	$self->error("invalid price"), return unless defined $n;
	$self->{'price'} = $n;
}

sub _h_pricegst
{
	my ($self, $dot, @args) = @_;
	$self->error(".PriceGST without prior .Item"), return
		unless defined $self->{'iline'};
	$self->error("only one .PriceGST allowed"), return
		if defined $self->{'pricegst'};
	$self->error(".PriceGST missing argument"), return
		unless @args && length $args[0];
	my $n = $self->make_money($args[0]);
	$self->error("invalid price"), return unless defined $n;
	$self->{'pricegst'} = $n;
}

sub _enditem
{
	my ($self) = @_;
	my $iline = $self->{'iline'};
	my $ia = $self->{'iaccount'};
	my $pricegst = $self->{'pricegst'};
	my $price = $self->{'price'};
	my $gst = $self->{'gst'};
	undef $self->{'iline'};
	undef $self->{'iaccount'};
	undef $self->{'pricegst'};
	undef $self->{'price'};
	undef $self->{'gst'};
	if (defined $price) {
		if (defined $gst) {
			if (defined $pricegst) {
				$self->_error("line ", $self->{'iline'}, ": illegal values: .Price + .GST != .PriceGST") if
					$price + $gst != $pricegst;
			}
		}
		elsif (defined $pricegst) {
			$self->_error("line ", $self->{'iline'}, ": illegal values: .Price > .PriceGST") if
				$price > $pricegst;
			$gst = $pricegst - $price;
		}
		else {
			my $gstf = $self->_config->var('gst_factor');
			$self->_error("line ", $self->{'iline'}, ": missing .GST") if
				!defined $gstf;
			$gst = $price * $gstf;
		}
	}
	elsif (defined $pricegst) {
		if (defined $gst) {
			$self->_error("line ", $self->{'iline'}, ": illegal values: .GST > .PriceGST") if
				$gst > $pricegst;
		}
		else {
			my $gstf = $self->_config->var('gst_factor');
			$self->_error("line ", $self->{'iline'}, ": missing .GST") if
				!defined $gstf;
			$gst = $pricegst / (1.0 + $gstf);
		}
		$price = $pricegst - $gst;
	}
	else {
		$self->_error("line ", $self->{'iline'}, ": missing .Price or .PriceGST");
	}
	$ia = $self->_map_account($ia) if length $ia;
	#return undef unless defined $ia;
	$self->{'total-gst'} += $gst;
	push @{$self->{'items'}}, [$ia, $price, '', $iline];
}

sub _h_total
{
	my ($self, @args) = @_;
	$self->_enditem if defined $self->{'iline'};
	$self->SUPER::_h_total(@args);
}

sub _h_totalgst
{
	my ($self, $dot, @args) = @_;
	$self->error(".TotalGST missing argument"), return
		unless @args && length $args[0];
	my $n = $self->make_money($args[0]);
	$self->error("invalid price"), return unless defined $n;
	$self->{'totgstline'} = $self->_parser->linenum;
	$self->{'totalgst'} = $n;
}

sub _h_due
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Due or .Terms allowed"), return
		if defined $self->{'terms'};
	$self->error("only one .Due allowed"), return
		if defined $self->{'due'};
	$self->{'due'} = '';
	my $dstr = join ' ', @args;
	$self->error(".Due missing arguments"), return unless length $dstr;
	my $date = $self->make_date($dstr) or return;
	$self->{'due'} = $date;
}

sub _h_terms
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Due or .Terms allowed"), return
		if defined $self->{'due'};
	$self->error("only one .Terms allowed"), return
		if defined $self->{'terms'};
	$self->{'terms'} = '';
	$self->error(".Terms missing argument"), return
		unless @args && length $args[0];
	$self->error(".Terms argument must be a number of days"), return
		unless $args[0] =~ /^\d+$/o;
	$self->{'terms'} = $args[0] + 0;
}

1;
