#!/usr/bin/env python3

import logging
import requests
import datetime
import abo.trybooking.config as config
import abo.trybooking.model as model

class Client(object):

    def __init__(self):
        self._events = None
        self._bookings = None

    def _get(self, url):
        logging.debug(f'url = {url}')
        r = requests.get(url, auth=(config.get().api_key, config.get().api_secret))
        json = r.json()
        logging.debug(f'json = {json!r}')
        return json

    def get_events_json(self):
        return self._get("https://api.trybooking.com/AU/reporting/v1/event")

    def get_events(self):
        for json_item in self.get_events_json():
            yield model.Event.from_json_data(json_item)

    def get_account_json(self):
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=365)
        return self._get(f"https://api.trybooking.com/AU/reporting/v1/account?startDate={start.strftime(r'%Y-%m-%d')}&endDate={end.strftime(r'%Y-%m-%d')}")

    def get_booking_json(self, booking_id):
        return self._get(f"https://api.trybooking.com/AU/reporting/v1/bookings/{booking_id}")

    def get_bookings(self):
        booking_ids = dict()
        for transaction in model.Account.from_json_data(self.get_account_json()).transactions:
            # Fund transfers do not correspond to a booking.
            if transaction.booking_id:
                if transaction.booking_id not in booking_ids or transaction.date_time < booking_ids[transaction.booking_id].date_time:
                    booking_ids[transaction.booking_id] = transaction
        for booking_id in sorted(booking_ids, key=lambda id: booking_ids[id].date_time):
            #print(booking_id, booking_ids[booking_id].date_time.strftime(r'%-d-%-b-%Y %H:%M:%S %z %Z'))
            yield model.Booking.from_json_data(self.get_booking_json(booking_id)[0])

    def events(self):
        if self._events is None:
            self._events = list(self.get_events())
        return iter(self._events)

    def bookings(self):
        if self._bookings is None:
            self._bookings = list(self.get_bookings())
        return iter(self._bookings)
