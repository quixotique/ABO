package ABO::Document::Common_Groff;
use feature 'unicode_strings';

sub _parser { shift->{'parser'} }

sub _error
{
	my $self = shift;
	$self->{'error'} = 1;
	$self->error(@_);
}

sub _syntax
{
	my $self = shift;
	$self->_error("line ", $self->_parser->linenum, ": syntax error: ", @_);
}

sub _check_has_date
{
	my $self = shift;
	$self->_error("missing .Date") unless defined $self->{'date'};
}

sub _check_has_ref
{
	my $self = shift;
	$self->_error("missing .Ref") unless defined $self->{'ref'};
}

sub _check_has_account
{
	my $self = shift;
	$self->_error("missing .Account") unless defined $self->{'account'};
}

sub _check_has_customer
{
	my $self = shift;
	$self->_error("missing .Customer") unless defined $self->{'customer'};
}

sub _check_has_total
{
	my $self = shift;
	$self->_error("missing .Total") unless defined $self->{'total'};
}

sub _check_has_gst
{
	my $self = shift;
	$self->_error("missing .GST") unless defined $self->{'gst'};
}

sub _h_text
{
	my ($self, $text) = @_;
	if ($self->{'cflag'})
	{
		$text =~ s/^\s+//o;
		$text =~ s/\s+$//o;
		$text =~ s/\s{2,}/ /go;
		$self->{'customer'} = $text;
		undef $self->{'cflag'};
	}
}

sub _h_ref
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Ref allowed"), return
		if defined $self->{'ref'};
	$self->{'ref'} = '';
	$self->error(".Ref missing argument"), return
		unless @args && length $args[0];
	$self->{'ref'} = $args[0];
}

sub _h_date
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Date allowed"), return
		if defined $self->{'date'};
	$self->{'date'} = '';
	my $dstr = join ' ', @args;
	$self->error(".Date missing arguments"), return unless length $dstr;
	my $date = $self->make_date($dstr) or return;
	$self->{'date'} = $date;
}

sub _h_account
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Account allowed"), return
		if defined $self->{'account'};
	$self->{'account'} = '';
	$self->error(".Account missing argument"), return
		unless @args && length $args[0];
	$self->{'acline'} = $self->_parser->linenum;
	$self->{'account'} = $args[0];
}

sub _h_customer
{
	my ($self, $dot, @args) = @_;
	$self->error("only one .Customer allowed"), return
		if defined $self->{'customer'};
	$self->{'customer'} = '';
	$self->{'cflag'} = 1;
}

sub _h_total
{
	my ($self, $dot, @args) = @_;
	$self->error(".Total missing argument"), return
		unless @args && length $args[0];
	my $n = $self->make_money($args[0]);
	$self->error("invalid price"), return unless defined $n;
	$self->{'totline'} = $self->_parser->linenum;
	$self->{'total'} = $n;
}

sub _h_gst
{
	my ($self, $dot, @args) = @_;
	$self->error(".GST missing argument"), return
		unless @args && length $args[0];
	my $n = $self->make_money($args[0]);
	$self->error("invalid price"), return unless defined $n;
	$self->{'gstline'} = $self->_parser->linenum;
	$self->{'gst'} = $n;
}

1;
