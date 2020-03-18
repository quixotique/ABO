#!/usr/bin/env python3

import sys
import os
import requests
import datetime
import abo.trybooking.config as config
import abo.trybooking.model as model

def fatal(message, status=1):
    print("%s: %s" % (os.path.basename(sys.argv[0]), message), file=sys.stderr)
    sys.exit(status)

def main():
    try:
        c = config.Config().load()
    except config.ConfigException as e:
        fatal(f'configuration error: {e}')
    if len(sys.argv) < 2:
        fatal(f'missing arg')
    if len(sys.argv) > 2:
        fatal(f'spurious args')
    arg = sys.argv[1]
    if arg == 'events':
        r = requests.get("https://api.trybooking.com/AU/reporting/v1/event", auth=(c.api_key, c.api_secret))
        events = []
        for json_data in r.json():
            events.append(model.Event.from_json_data(json_data))
        for event in events:
            print(event.name)
            print("  ", event.session.start_datetime.strftime(r'%-d-%-b-%Y %H:%M:%S %z %Z'))
            print("  ", event.session.status)
            print("  ", repr(event))
            for session in event.sessions:
                print("      ", repr(session))
    elif arg == 'bookings':
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=365)
        url = f"https://api.trybooking.com/AU/reporting/v1/account?startDate={start.strftime(r'%Y-%m-%d')}&endDate={end.strftime(r'%Y-%m-%d')}"
        print(url)
        r = requests.get(url, auth=(c.api_key, c.api_secret))
        json = r.json()
        account = model.Account.from_json_data(json)
        #print(repr(account))
        booking_ids = dict()
        for transaction in account.transactions:
            # Fund transfers do not correspond to a booking.
            if transaction.booking_id:
                if transaction.booking_id not in booking_ids or transaction.date_time < booking_ids[transaction.booking_id].date_time:
                    booking_ids[transaction.booking_id] = transaction
        for booking_id in sorted(booking_ids, key=lambda id: booking_ids[id].date_time):
            #print(booking_id, booking_ids[booking_id].date_time.strftime(r'%-d-%-b-%Y %H:%M:%S %z %Z'))
            url = f"https://api.trybooking.com/AU/reporting/v1/bookings/{booking_id}"
            print(url)
            r = requests.get(url, auth=(c.api_key, c.api_secret))
            json = r.json()
            print(repr(json))
            booking = model.Booking.from_json_data(json[0])
            print(repr(booking))
            for ticket in booking.tickets:
                print("   ", repr(ticket))

if __name__ == '__main__':
    main()
