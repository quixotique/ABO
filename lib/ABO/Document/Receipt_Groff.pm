package ABO::Document::Receipt_Groff;
use feature 'unicode_strings';

use ABO::Document::Receipt_Common;
use ABO::Document::Parser;
use ABO::Document::Common_Groff;
@ISA = qw(
	ABO::Document::Receipt_Common
	ABO::Document::Parser
	ABO::Document::Common_Groff
);
use Groff::Parser;

sub probe
{
	shift if @_ && UNIVERSAL::isa($_[0], __PACKAGE__);
	local $_ = shift;
	return scalar m/^([.']\S.*\n)*[.'](TaxReceipt|Receipt)(\s|$)/o;
}

sub _parse_receipt
{
	my ($self, $body) = @_;

	$self->{'parser'} = Groff::Parser->new(
		text => sub { $self->_h_text(@_) },
		request => {
			Ref => sub { $self->_h_ref(@_) },
			Date => sub { $self->_h_date(@_) },
			Account => sub { $self->_h_account(@_) },
			Customer => sub { $self->_h_customer(@_) },
			Deposit => sub { $self->_h_deposit(@_) },
			GST => sub { $self->_h_gst(@_) },
			Total => sub { $self->_h_total(@_) },
		}
	);

	$self->_parser->parse($body)->eof or return undef;

	$self->_check_has_ref;
	$self->_check_has_date;
	$self->_check_has_account;
	$self->_check_has_deposit;
	$self->_check_has_customer;
	$self->_check_has_total;

	if (defined $self->{'gst'})
	{
		my $gstf = $self->_config->var('gst_factor');
		if (defined($self->{'total'}) && defined($gstf))
		{
			my $gst = $self->{'total'} * $gstf;
			$self->error("line ", $self->{'gstline'}, ": gst `", $self->{'gst'}, "' is not equal to total ", $self->{'total'}, " times $gstf = $gst")
				unless $gst == $self->{'gst'};
		}
	}

	return undef if $self->{'error'};

	$self->_set_attribute('Date', $self->{'date'});
	$self->_set_attribute('Account', $self->{'account'});
	$self->_set_attribute('Deposit', $self->{'deposit'});
	$self->_set_attribute('Customer', $self->{'customer'});
	$self->_set_attribute('Total', $self->{'total'});
	$self->_set_attribute('GST', $self->{'gst'}) if defined $self->{'gst'};

	return $self;
}

sub _check_has_deposit
{
	my $self = shift;
	$self->_error("missing .Deposit") unless defined $self->{'deposit'};
}

sub _h_deposit
{
	my ($self, $dot, @args) = @_;
	$self->_syntax("only one .Deposit allowed"), return
		if defined $self->{'deposit'};
	$self->{'deposit'} = '';
	$self->_syntax(".Deposit missing argument"), return
		unless @args && length $args[0];
	$self->{'deposit'} = $args[0];
}

1;
