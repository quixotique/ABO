#!/usr/bin/env python3

import os.path
import configparser
from abo.config import find_config_file
from abo.config import ConfigException
from abo.money import Currency

class Config(object):

    def __init(self):
        self.api_key = None
        self.api_secret = None
        self.event_code = None
        self.discount_codes = dict()

    def load(self):
        config = configparser.ConfigParser()

        name = '.trybooking'
        trybooking_path = find_config_file(name)
        if not trybooking_path:
            raise ConfigException(f'file not found: {name}')
        config.read(trybooking_path)

        trybooking_event_path = find_config_file('.trybooking-event', stop_dir=os.path.dirname(trybooking_path))
        if trybooking_event_path:
            config.read(trybooking_event_path)

        try:
            self.api_key = config['api']['key']
            self.api_secret = config['api']['secret']
        except KeyError as e:
            raise ConfigException(f'missing option in {path}: {e}')

        try:
            self.event_code = config['event']['code']
        except KeyError:
            pass

        try:
            for code, amount in config['discount codes'].items():
                self.discount_codes[code] = Currency.AUD.parse_amount(amount)
        except AttributeError:
            pass

        return self

_config = None

def get():
    global _config
    if _config is None:
        _config = Config().load()
    return _config
