# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Transaction cache.
"""

import os
import os.path
import errno
import cPickle as pickle
import abo.config

class TransactionCache(object):

    def __init__(self, path, transaction_source):
        self.path = path
        self.transaction_source = transaction_source

    def cache_path(self):
        return os.path.join(abo.config.cache_dir_path(), os.path.abspath(self.path).replace('/', '%%'))

    def transactions(self, force=False):
        cpath = self.cache_path()
        if force or self.mtime(cpath) < self.mtime(self.path):
            transactions = self.transaction_source.transactions()
            try:
                os.makedirs(os.path.dirname(cpath))
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
            pickle.dump(transactions, file(cpath, 'w'))
            return transactions
        return pickle.load(file(cpath))

    @staticmethod
    def mtime(path):
        try:
            return os.stat(path).st_mtime
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            return -1
