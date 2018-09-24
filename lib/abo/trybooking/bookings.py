#!/usr/bin/env python3

import sys
import os
import re
from collections import namedtuple
import datetime

from abo.money import Money
import abo.trybooking.csv_reader as csv_reader

def clean_address(text):
    text = re.sub(r'(\d+)\s*([A-Za-z]{2,})', r'\1 \2', text)
    text = re.sub(r'(\d+)\s+([A-Z])\b', r'\1\2', text)
    return text

def capitalise_word(word):
    if re.fullmatch(r'\d+[A-Za-z]', word):
        return word.upper()
    return word.capitalize()

def capitalise_words(text):
    return ''.join(map(capitalise_word, re.split(r'(\W+)', text.lower())))

def parse_boolean(text):
    return text.strip().lower() in ('yes', 'on', 'true', '1')

def parse_optional_text(text):
    if re.sub(r'[^a-z]', '', text.lower()) in ('', 'no', 'none', 'na', 'nil'):
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
                   telephone = re.sub(r'(\d{3})(\d{3})$', ' \\1 \\2', re.sub(r'\D', '', row.booking_telephone,)),
                   email = row.booking_email,
                   payment = Money.AUD.from_text(row.payment_received),
                   discount = Money.AUD.from_text(row.discount_amount),
                   processing_fees = Money.AUD.from_text(row.processing_fees),
                   datetime = datetime.datetime.strptime(row.date_booked + ' ' + row.time_booked, '%d/%m/%Y %I:%M:%S %p')
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
                       payment,
                       discount,
                       processing_fees,
                       datetime):
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
        self.payment = payment
        self.discount = discount
        self.processing_fees = processing_fees
        self.datetime = datetime
        self._tickets = []

    def add_ticket(self, ticket):
        assert ticket._booking is None
        ticket._booking = self
        self._tickets.append(ticket)

    @property
    def tickets(self):
        return iter(self._tickets)

    @property
    def ticket_count(self):
        return len(self._tickets)

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join('%s=%r' % (a, v) for a, v in self.__dict__.items() if not a.startswith('_')) + ')'

class Ticket(object):

    @classmethod
    def from_csv_row(cls, row):
        def optional(func):
            try:
                return func()
            except AttributeError:
                return None
        return cls( type = row.ticket_type,
                    price = Money.AUD.from_text(row.ticket_price),
                    name = optional(lambda: row.ticket_data_name),
                    age = optional(lambda: int(row.ticket_data_age)),
                    instrument = optional(lambda: capitalise_words(row.ticket_data_instrument)),
                    photo_consent = optional(lambda: parse_boolean(row.ticket_data_photo_consent)),
                    health_concerns = optional(lambda: parse_optional_text(row.ticket_data_health_concerns)),
                )

    def __init__(self, type,
                       price,
                       name = None,
                       age = None,
                       instrument = None,
                       photo_consent = None,
                       health_concerns = None):
        self.type = type
        self.price = price
        self.name = name
        self.age = age
        self.instrument = instrument
        self.photo_consent = photo_consent
        self.health_concerns = health_concerns
        self._booking = None

    @property
    def booking(self):
        return self._booking

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join('%s=%r' % (a, v) for a, v in self.__dict__.items() if not a.startswith('_')) + ')'

class Bookings(object):

    def __init__(self):
        self._bookings = []
        self._tickets = []

    def read_csv(self, path):
        reader = csv_reader.reader(open(path, newline='', encoding='utf-8-sig'))
        booking_by_id = dict()
        for row in reader:
            ticket = Ticket.from_csv_row(row)
            booking = Booking.from_csv_row(row)
            self._tickets.append(ticket)
            if booking.id in booking_by_id:
                booking = booking_by_id[booking.id]
            else:
                booking_by_id[booking.id] = booking
                self._bookings.append(booking)
            booking.add_ticket(ticket)
        self._tickets.sort(key= lambda t: (t.booking.datetime, t.name))
        self._bookings.sort(key= lambda b: b.datetime)
        return self

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
