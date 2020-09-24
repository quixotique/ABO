#!/usr/bin/env python3

import sys
import os
import re
import datetime
import logging
import inspect

from abo.money import Money
import abo.trybooking.config as config
import abo.trybooking.csv_reader as csv_reader
import abo.trybooking.client as trybooking_client

def non_blank_str(text):
    if not isinstance(text, str):
        raise TypeError('must be string')
    if not text or text.isspace():
        raise ValueError('must not be blank')
    return text

def non_negative_int(value):
    if not isinstance(value, int):
        raise TypeError('must be integer')
    if value < 0:
        raise ValueError('must not be negative')
    return value

def boolean(value):
    if not isinstance(value, bool):
        raise TypeError('must be boolean')
    return value

def parse_json_date_time(text):
    # Trybooking represents all date/time values in the UTC time zone.  Return
    # a datetime object that is in the local time zone.
    return datetime.datetime.strptime(text, r'%Y-%m-%dT%H:%M:%SZ') \
                .replace(tzinfo=datetime.timezone.utc) \
                .astimezone()

def optional(func, fallback=None):
    try:
        return func()
    except AttributeError:
        return fallback

def clean_name(text):
    return ' '.join(text.split())

def clean_address(text):
    text = re.sub(r'(\d+)\s*([A-Za-z]{2,})', r'\1 \2', text)
    text = re.sub(r'(\d+)\s+([A-Z])\b', r'\1\2', text)
    return text

def clean_money(text):
    text = re.sub(r'(\d+\.\d\d)00', r'\1', text)
    return text

def capitalise_word(word):
    if re.fullmatch(r'\d+[A-Za-z]', word):
        return word.upper()
    return word.capitalize()

def capitalise_words(text):
    return ''.join(map(capitalise_word, re.split(r'(\W+)', text.lower())))

def parse_boolean(text):
    return text.strip().lower() in ('yes', 'on', 'true', '1')

def extract_int(value):
    return int(re.sub(r'\D*(\d+).*', r'\1', value)) if isinstance(value, str) else int(value)

def parse_telephone(text):
    digits = re.sub(r'\D', '', text.strip().lower())
    if len(digits) == 8:
        return digits[:4] + ' ' + digits[4:]
    if len(digits) == 9 and digits[0] == '4':
        digits = '0' + digits
    if len(digits) == 11 and digits[:2] == '61':
        digits = '0' + digits[2:]
    return re.sub(r'(\d{3})(\d{3})$', ' \\1 \\2', digits)

def parse_optional_text(text):
    if re.sub(r'[^0-9a-z]', '', text.lower()) in ('', 'no', 'none', 'na', 'nil'):
        return None
    return text

def extract_collected_data(json_collected_data, key):
    for item in json_collected_data:
        if item['label'] == key:
            return item['value']
    return None

def generic_repr(obj):
    if isinstance(obj, datetime.datetime):
        return 'datetime(' + obj.strftime(r'%d/%m/%Y %H:%M:%S (%z) %Z') + ')'
    if isinstance(obj, list):
        return '[' + ', '.join(shallow_repr(v) for v in obj) + ']'
    if hasattr(obj, '__dict__'):
        return type(obj).__name__ + '(' + ', '.join('%s=%s' % (a, shallow_repr(v)) for a, v in obj.__dict__.items()) + ')'
    return repr(obj)

def shallow_repr(obj):
    if getattr(obj, '__module__', '').startswith('abo.trybooking.'):
        return type(obj).__name__
    return generic_repr(obj)

class Account(object):

    @classmethod
    def from_json_data(cls, json_data):
        account = cls(id =               json_data['accountId'],
                      pending_transfer = json_data['pendingFundTransfer'],
                      balance =          json_data['balance'])
        for json_data_transaction in json_data['transactions']:
            transaction = Transaction.from_json_data(json_data_transaction)
            transaction._account = account
            account._transactions.append(transaction)
        return account

    def __init__(self, id,
                       pending_transfer,
                       balance):
        self.id = id
        self.pending_transfer = pending_transfer
        self.balance = balance
        self._transactions = []

    @property
    def transactions(self):
        return list(self._transactions)

    def __repr__(self):
        return generic_repr(self)

class Transaction(object):

    @classmethod
    def from_json_data(cls, json_data):
        return cls(type =             json_data['transactionTypeName'],
                   date_time =        parse_json_date_time(json_data['transactionDate']),
                   description =      json_data['description'],
                   debit =            json_data['debitAmount'],
                   credit =           json_data['creditAmount'],
                   customer_name =    json_data['customerName'],
                   booking_id =       json_data['bookingURLId'])

    def __init__(self, type,
                       date_time,
                       description,
                       debit,
                       credit,
                       customer_name,
                       booking_id):
        self.type = type
        self.date_time = date_time
        self.description = description
        self.debit = debit
        self.credit = credit
        self.customer_name = customer_name
        self.booking_id = booking_id
        self._account = None

    def __repr__(self):
        return generic_repr(self)

class Event(object):

    @classmethod
    def from_json_data(cls, json_data):
        event = cls(code =               json_data['eventCode'],
                    name =               json_data['name'],
                    description =        json_data['description'],
                    venue =              json_data['venue'],
                    contact_name =       json_data['contactName'],
                    contact_email =      json_data['contactEmail'],
                    contact_phone =      json_data['contactNumber'],
                    is_public =          json_data['isPublic'],
                    is_open =            json_data['isOpen'],
                    allow_waiting_list = json_data['allowWaitingList'],
                    time_zone =          json_data['timeZone'],
                    booking_url =        json_data['bookingUrl'],
                    homepage_template =  json_data['homepageTemplate'])
        for json_data_session in json_data['sessionList']:
            session = Session.from_json_data(json_data_session)
            session._event = event
            event._sessions.append(session)
        return event

    def __init__(self, code,
                       name,
                       description,
                       venue,
                       contact_name,
                       contact_email,
                       contact_phone,
                       is_public,
                       is_open,
                       allow_waiting_list,
                       time_zone,
                       booking_url,
                       homepage_template):
        self.code = non_blank_str(code)
        self.name = name
        self.description = description
        self.venue = venue
        self.contact_name = contact_name
        self.contact_email = contact_email
        self.contact_phone = parse_telephone(contact_phone)
        self.is_public = boolean(is_public)
        self.is_open = boolean(is_open)
        self.allow_waiting_list = boolean(allow_waiting_list)
        self.time_zone = time_zone
        self.booking_url = booking_url
        self.homepage_template = homepage_template
        self._sessions = []

    @property
    def sessions(self):
        return list(self._sessions)

    @property
    def session(self):
        assert len(self._sessions) == 1
        return self._sessions[0]

    def __repr__(self):
        return generic_repr(self)

class Session(object):

    @classmethod
    def from_json_data(cls, json_data):
        return cls(id =                     json_data['id'],
                   description =            json_data['description'],
                   alternate_label =        json_data['alternateLabel'],
                   start_datetime =         parse_json_date_time(json_data['eventStartDate']),
                   end_datetime =           parse_json_date_time(json_data['eventEndDate']),
                   booking_open_datetime =  parse_json_date_time(json_data['bookingStartDate']),
                   booking_close_datetime = parse_json_date_time(json_data['bookingEndDate']),
                   status =                 json_data['sessionStatus'],
                   capacity =               json_data['sessionCapacity'],
                   availability =           json_data['sessionAvailability'],
                   booking_url =            json_data['sessionBookingUrl'])

    def __init__(self, id,
                       description,
                       alternate_label,
                       start_datetime,
                       end_datetime,
                       booking_open_datetime,
                       booking_close_datetime,
                       status,
                       capacity,
                       availability,
                       booking_url):
        self.id = non_negative_int(id)
        self.description = description
        self.alternate_label = alternate_label
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.booking_open_datetime = booking_open_datetime
        self.booking_close_datetime = booking_close_datetime
        self.status = non_blank_str(status)
        self.capacity = non_negative_int(capacity)
        self.availability = non_negative_int(availability)
        self.booking_url = booking_url
        self._event = None

    @property
    def event(self):
        return self._event

    def __repr__(self):
        return generic_repr(self)

class Booking(object):

    @classmethod
    def from_json_data(cls, json_data):
        booking = cls(id =                 json_data['bookingUrlId'],
                      date_time =          parse_json_date_time(json_data['date']),
                      first_name =         json_data['bookingFirstName'],
                      last_name =          json_data['bookingLastName'],
                      address_1 =          json_data['bookingAddress1'],
                      address_2 =          json_data['bookingAddress2'],
                      suburb =             json_data['bookingCity'],
                      state =              json_data['bookingState'],
                      post_code =          json_data['bookingPostCode'],
                      telephone =          json_data['bookingPhone'],
                      email =              json_data['bookingEmail'],
                      emergency_contact =  extract_collected_data(json_data['bookingDataCollections'], 'Emergency contact'),
                      total_payment =      Money.AUD(json_data['totalAmount']),
                      discount =           Money.AUD(0), # accumulated below
                      processing_fees =    Money.AUD(json_data['totalProcessingFee']),
                     )
        for json_data_ticket in json_data['bookingTickets']:
            ticket = Ticket.from_json_data(json_data_ticket)
            ticket._booking = booking
            booking._tickets.append(ticket)
            booking._discount += ticket.discount
        return booking

    @classmethod
    def from_csv_row(cls, row):
        return cls(id = row.booking_id,
                   date_time =          datetime.datetime.strptime(row.date_booked + ' ' + row.time_booked, '%d/%m/%Y %I:%M:%S %p').astimezone(),
                   first_name =         row.booking_first_name,
                   last_name =          row.booking_last_name,
                   address_1 =          row.booking_address_1,
                   address_2 =          row.booking_address_2,
                   suburb =             row.booking_suburb,
                   state =              row.booking_state,
                   post_code =          row.booking_post_code,
                   telephone =          row.booking_telephone,
                   email =              row.booking_email,
                   emergency_contact =  row.booking_data_emergency_contact,
                   net_payment =        Money.AUD.from_text(row.net_booking),
                   discount =           Money.AUD.from_text(row.discount_amount),
                   processing_fees =    Money.AUD.from_text(row.processing_fees),
                )

    def __init__(self, id,
                       date_time,
                       first_name,
                       last_name,
                       address_1,
                       address_2,
                       suburb,
                       state,
                       post_code,
                       telephone,
                       email,
                       emergency_contact,
                       discount,
                       processing_fees,
                       total_payment = None,
                       net_payment = None
                ):
        self.id = id
        self.date_time = date_time
        self.first_name = capitalise_words(clean_name(first_name))
        self.last_name = capitalise_words(clean_name(last_name))
        self.address_1 = capitalise_words(clean_address(address_1))
        self.address_2 = capitalise_words(clean_address(address_2))
        self.suburb = capitalise_words(suburb)
        self.state = state.upper()
        self.post_code = int(post_code) if post_code else None
        self.telephone = parse_telephone(telephone)
        self.email = email
        self.emergency_contact = optional(lambda: parse_telephone(emergency_contact))
        self._total_payment = total_payment
        self._net_payment = net_payment
        self._real_total_payment = None
        self._real_net_payment = None
        self._discount = discount
        self._real_discount = None
        self._processing_fees = processing_fees
        self._real_processing_fees = None
        self._refund = None
        self._tickets = []

    def add_ticket(self, ticket):
        assert ticket._booking is None
        ticket._booking = self
        self._tickets.append(ticket)

    @property
    def total_payment(self):
        # Trybooking omits refunded tickets it its reported booking payment, so reconstruct the
        # original payment by summing all the ticket prices, less their discounts.
        if self._real_total_payment is None:
            self._real_total_payment = sum(t.price - t.discount for t in self._tickets)
            if self._total_payment is not None and self._total_payment != self._real_total_payment:
                logging.warn(f'correct total payment {self._total_payment} to {self._real_total_payment}: {self.first_name} {self.last_name} {self.date_time.date()}')
        return self._real_total_payment

    @property
    def net_payment(self):
        if self._real_net_payment is None:
            self._real_net_payment = self.total_payment - self.processing_fees
            if self._net_payment is not None and self._net_payment != self._real_net_payment:
                logging.warn(f'correct net payment {self._net_payment} to {self._real_net_payment}: {self.first_name} {self.last_name} {self.date_time.date()}')
        return self._real_net_payment

    @property
    def discount(self):
        # A booking's discount should equal the sum of the discounts of all its tickets, including
        # refunded ones.
        if self._real_discount is None:
            self._real_discount = sum(t.discount for t in self._tickets)
            if self._discount != self._real_discount:
                logging.warn(f'correct discount {self._discount} to {self._real_discount}: {self.first_name} {self.last_name} {self.date_time.date()}')
        return self._real_discount

    @property
    def processing_fees(self):
        if self._real_processing_fees is None:
            # Trybooking CSV files sometimes report an erroneous processing fees amount (out by
            # 0.01), so calculate the correct processing fees by summing the prices of all
            # non-refunded tickets, less their discounts, and taking the difference between that and
            # the reported net booking payment, which is correct.
            if self._net_payment is not None:
                calculated_total_payment = sum(t.price - t.discount for t in self._tickets if not t.refunded)
                self._real_processing_fees = calculated_total_payment - self._net_payment
                if self._processing_fees != self._real_processing_fees:
                    logging.warn(f'correct processing fee {self._processing_fees} to {self._real_processing_fees}: {self.first_name} {self.last_name} {self.date_time.date()}')
            else:
                self._real_processing_fees = self._processing_fees
        return self._real_processing_fees

    @property
    def refund(self):
        # The refunded amount is the difference between the original payment and the reported
        # payment.
        if self._refund is None:
            self._refund = self.payment - self._payment
            logging.info(f'calculate refund of {self._refund}: {self.first_name} {self.last_name}')
        return self._refund

    @property
    def tickets(self):
        return list(self._tickets)

    def __repr__(self):
        return generic_repr(self)

class Ticket(object):

    @classmethod
    def from_json_data(cls, json_data):
        discount = Money.AUD(json_data['discountAmount'])
        refunded_amount = Money.AUD(json_data['refundedAmount'])
        return cls( type =              json_data['ticketName'],
                    event_code =        json_data['eventCode'],
                    price =             Money.AUD(json_data['totalTicketPrice']),
                    discount =          discount,
                    first_name =        extract_collected_data(json_data['bookingTicketDataCollections'], 'Attendee First Name'),
                    last_name =         extract_collected_data(json_data['bookingTicketDataCollections'], 'Attendee Last Name'),
                    age =               extract_collected_data(json_data['bookingTicketDataCollections'], 'Age'),
                    instrument =        extract_collected_data(json_data['bookingTicketDataCollections'], 'Instrument'),
                    photo_consent =     extract_collected_data(json_data['bookingTicketDataCollections'], 'Photo consent'),
                    health_concerns =   extract_collected_data(json_data['bookingTicketDataCollections'], 'Health concerns'),
                    void =              json_data['isVoid'],
                    refunded =          refunded_amount != 0,
                    refunded_amount =   refunded_amount - discount if refunded_amount != 0 else Money.AUD(0),
                )

    @classmethod
    def from_csv_row(cls, row, discount_codes={}):
        price = Money.AUD.from_text(row.ticket_price)
        code = row.promotion_discount_code
        discount = discount_codes[code] if code else Money.AUD(0)
        # Trybooking omits the discount from the ticket price and the refunded amount if a refund
        # has been made, so we have to deduce the original ticket price ourselves.
        refunded = optional(lambda: row.ticket_status.strip().lower() == 'refunded', False)
        refunded_amount = None
        if refunded:
            refunded_amount = Money.AUD.from_text(clean_money(row.ticket_refunded_amount)) - discount
        return cls( type =              row.ticket_type,
                    event_code =        None,
                    price =             price,
                    discount =          discount,
                    first_name =        optional(lambda: row.ticket_data_attendee_first_name),
                    last_name =         optional(lambda: row.ticket_data_attendee_last_name),
                    age =               optional(lambda: row.ticket_data_age),
                    instrument =        optional(lambda: row.ticket_data_instrument),
                    photo_consent =     optional(lambda: row.ticket_data_photo_consent),
                    health_concerns =   optional(lambda: row.ticket_data_health_concerns),
                    void =              optional(lambda: parse_boolean(row.void), False),
                    refunded =          refunded,
                    refunded_amount =   refunded_amount,
                )

    def __init__(self, type,
                       event_code,
                       price,
                       discount,
                       first_name,
                       last_name,
                       age = None,
                       instrument = None,
                       photo_consent = None,
                       health_concerns = None,
                       void = False,
                       refunded = False,
                       refunded_amount = None):
        self.type = type
        self.event_code = non_blank_str(event_code) if event_code else config.get().event_code
        self.price = price
        self.discount = discount
        self.first_name = (capitalise_words(clean_name(first_name)) if first_name else None) or None
        self.last_name = (capitalise_words(clean_name(last_name)) if last_name else None) or None
        self.age = extract_int(age) if age else None
        self.instrument = (capitalise_words(clean_name(instrument)) if instrument else None) or None
        self.photo_consent = parse_boolean(photo_consent) if photo_consent else None
        self.health_concerns = parse_optional_text(health_concerns) if health_concerns else None
        self.void = boolean(void)
        self.refunded = refunded
        self.refunded_amount = refunded_amount
        self._booking = None
        self._event = None

    @property
    def name(self):
        return ' '.join(filter(bool, [self.first_name, self.last_name]))

    @property
    def booking(self):
        return self._booking

    def __repr__(self):
        return generic_repr(self)

class Bookings(object):

    def __init__(self, with_extra_bookings=True):
        self._with_extra_bookings = with_extra_bookings
        self._event_codes = set()
        self._bookings = []
        self._tickets = []
        self._discount_codes = dict()
        # Load extra bookings from current working directory.  This may also add the relevant discount codes.
        sys.path.append('.')
        try:
            import extra_bookings
            extra_bookings.main(self)
            self._sort()
        except ImportError:
            pass

    def load(self, csv_path=None):
        if csv_path:
            self.read_csv(csv_path)
        else:
            self.fetch_from_site(config.get().event_code)
        return self

    def read_csv(self, path):
        reader = csv_reader.reader(open(path, newline='', encoding='utf-8-sig'))
        booking_by_id = dict()
        for row in reader:
            ticket = Ticket.from_csv_row(row, self._discount_codes)
            booking = Booking.from_csv_row(row)
            self._tickets.append(ticket)
            if booking.id in booking_by_id:
                booking = booking_by_id[booking.id]
            else:
                booking_by_id[booking.id] = booking
                self._bookings.append(booking)
            booking.add_ticket(ticket)
        self._prepare()
        return self

    def fetch_from_site(self, event_code=None):
        client = trybooking_client.Client()
        for booking in client.bookings():
            in_event = False
            for ticket in booking.tickets:
                if event_code is None or ticket.event_code == event_code:
                    self._tickets.append(ticket)
                    in_event = True
            if in_event:
                self._bookings.append(booking)
        self._prepare()
        return self

    def add_event_code(self, code):
        assert code != ''
        self._event_codes.add(code)

    def add_discount_code(self, code, amount):
        assert code != ''
        self._discount_codes[code] = Money.AUD(amount)

    def add_extra_booking(self, booking):
        if self._with_extra_bookings:
            self._bookings.append(booking)
            for ticket in booking.tickets:
                self._tickets.append(ticket)

    def _sort(self):
        self._tickets.sort(key= lambda t: (t.booking.date_time, t.name))
        self._bookings.sort(key= lambda b: b.date_time)

    def _prepare(self):
        self._sort()
        for ticket in self._tickets:
            self.add_event_code(ticket.event_code)

    @property
    def event_codes(self):
        return iter(self._event_codes)

    @property
    def event_code(self):
        assert len(self._event_codes) == 1, f'self._event_codes = {self._event_codes!r}'
        return next(self.event_codes)

    @property
    def tickets(self):
        return iter(self._tickets)

    @property
    def bookings(self):
        return iter(self._bookings)

def main():
    tb = Bookings()
    tb.read_csv(sys.argv[1])
    for b in tb.bookings:
        print(repr(b))
        for t in b.tickets:
            print('   .add_ticket(' + repr(t) + ')')

if __name__ == '__main__':
    main()
