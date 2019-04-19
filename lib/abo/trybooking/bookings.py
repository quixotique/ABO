#!/usr/bin/env python3

import sys
import os
import re
from collections import namedtuple
import datetime

from abo.money import Money
import abo.trybooking.csv_reader as csv_reader

def optional(func, fallback=None):
    try:
        return func()
    except AttributeError:
        return fallback

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

def extract_int(text):
    return int(re.sub(r'\D*(\d+).*', r'\1', text))

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

class Booking(object):

    @classmethod
    def from_csv_row(cls, row):
        return cls(id = row.booking_id,
                   first_name = capitalise_words(row.booking_first_name),
                   last_name = capitalise_words(row.booking_last_name),
                   address_1 = capitalise_words(clean_address(row.booking_address_1)),
                   address_2 = capitalise_words(clean_address(row.booking_address_2)),
                   suburb = capitalise_words(row.booking_suburb),
                   state = row.booking_state.upper(),
                   post_code = int(row.booking_post_code),
                   telephone = parse_telephone(row.booking_telephone),
                   email = row.booking_email,
                   emergency_contact = optional(lambda: parse_telephone(row.booking_data_emergency_contact)),
                   payment = Money.AUD.from_text(row.payment_received),
                   discount = Money.AUD.from_text(row.discount_amount),
                   processing_fees = Money.AUD.from_text(row.processing_fees),
                   datetime = datetime.datetime.strptime(row.date_booked + ' ' + row.time_booked, '%d/%m/%Y %I:%M:%S %p'),
                )

    def __init__(self, id,
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
                       payment,
                       discount,
                       processing_fees,
                       datetime
                ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.address_1 = address_1
        self.address_2 = address_2
        self.suburb = suburb
        self.state = state
        self.post_code = post_code
        self.telephone = telephone
        self.email = email
        self.emergency_contact = emergency_contact
        self._payment = payment
        self._real_payment = None
        self._discount = discount
        self._real_discount = None
        self._processing_fees = processing_fees
        self._real_processing_fees = None
        self._refund = None
        self.datetime = datetime
        self._tickets = []

    def add_ticket(self, ticket):
        assert ticket._booking is None
        ticket._booking = self
        self._tickets.append(ticket)

    @property
    def payment(self):
        # Trybooking omits refunded tickets it its reported booking payment, so reconstruct the
        # original payment by summing all the ticket prices, less their discounts, and less the
        # (correct) processing fees.
        if self._real_payment is None:
            self._real_payment = sum(t.price - t.discount for t in self._tickets) - self.processing_fees
            if self._payment != self._real_payment:
                print(f'correct payment {self._payment} to {self._real_payment}: {self.first_name} {self.last_name} {self.datetime.date()}', file=sys.stderr)
        return self._real_payment

    @property
    def discount(self):
        # A booking's discount should equal the sum of the discounts of all its tickets, including
        # refunded ones.
        if self._real_discount is None:
            self._real_discount = sum(t.discount for t in self._tickets)
            if self._discount != self._real_discount:
                print(f'correct discount {self._discount} to {self._real_discount}: {self.first_name} {self.last_name} {self.datetime.date()}', file=sys.stderr)
        return self._real_discount

    @property
    def processing_fees(self):
        if self._real_processing_fees is None:
            # Trybooking sometimes reports an erroneous processing fees amount (out by 0.01), so
            # calculate the correct processing fees by summing the prices of all non-refunded
            # tickets, less their discounts, and taking the difference between that and the reported
            # booking payment, which is correct.
            calculated_payment = sum(t.price - t.discount for t in self._tickets if not t.refunded)
            self._real_processing_fees = calculated_payment - self._payment
            if self._processing_fees != self._real_processing_fees:
                print(f'correct processing fee {self._processing_fees} to {self._real_processing_fees}: {self.first_name} {self.last_name} {self.datetime.date()}', file=sys.stderr)
        return self._real_processing_fees

    @property
    def refund(self):
        # The refunded amount is the difference between the original payment and the reported
        # payment.
        if self._refund is None:
            self._refund = self.payment - self._payment
            print(f'calculate refund of {self._refund}: {self.first_name} {self.last_name}', file=sys.stderr)
        return self._refund

    @property
    def tickets(self):
        return list(self._tickets)

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join('%s=%r' % (a, v) for a, v in self.__dict__.items() if not a.startswith('_')) + ')'

class Ticket(object):

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
        return cls( type = row.ticket_type,
                    price = price,
                    discount = discount,
                    first_name = capitalise_words(row.ticket_data_attendee_first_name),
                    last_name = capitalise_words(row.ticket_data_attendee_last_name),
                    age = optional(lambda: extract_int(row.ticket_data_age)),
                    instrument = optional(lambda: capitalise_words(row.ticket_data_instrument)),
                    photo_consent = optional(lambda: parse_boolean(row.ticket_data_photo_consent)),
                    health_concerns = optional(lambda: parse_optional_text(row.ticket_data_health_concerns)),
                    void = optional(lambda: parse_boolean(row.void), False),
                    refunded = refunded,
                    refunded_amount = refunded_amount,
                )

    def __init__(self, type,
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
        self.price = price
        self.discount = discount
        self.first_name = first_name
        self.last_name = last_name
        self.age = age
        self.instrument = instrument
        self.photo_consent = photo_consent
        self.health_concerns = health_concerns
        self.void = void
        self.refunded = refunded
        self.refunded_amount = refunded_amount
        self._booking = None

    @property
    def name(self):
        return ' '.join(filter(bool, [self.first_name, self.last_name]))

    @property
    def booking(self):
        return self._booking

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join('%s=%r' % (a, v) for a, v in self.__dict__.items() if not a.startswith('_')) + ')'

class Bookings(object):

    def __init__(self, with_extra_bookings=True):
        self._with_extra_bookings = with_extra_bookings
        self._bookings = []
        self._tickets = []
        self._discount_codes = {}
        sys.path.append('.')
        try:
            import extra_bookings
            extra_bookings.main(self)
            self._sort()
        except ImportError:
            pass

    def add_discount_code(self, code, amount):
        assert code != ''
        self._discount_codes[code] = Money.AUD(amount)

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
        self._sort()
        return self

    def add_extra_booking(self, booking):
        if self._with_extra_bookings:
            self._bookings.append(booking)
            for ticket in booking.tickets:
                self._tickets.append(ticket)

    def _sort(self):
        self._tickets.sort(key= lambda t: (t.booking.datetime, t.name))
        self._bookings.sort(key= lambda b: b.datetime)

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
