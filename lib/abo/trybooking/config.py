#!/usr/bin/env python3

import configparser
from abo.config import find_config_file
from abo.config import ConfigException

class Config(object):

    def __init(self):
        self.api_key = None
        self.api_secret = None

    def load(self):
        name = '.trybooking'
        path = find_config_file(name)
        if not path:
            raise ConfigException(f'file not found: {name}')
        config = configparser.ConfigParser()
        config.read(path)
        self.api_key = config['api']['key']
        self.api_secret = config['api']['secret']
        return self
