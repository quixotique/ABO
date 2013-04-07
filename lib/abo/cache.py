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

class FileCache(object):

    def __init__(self, path, contentfunc):
        self.path = path
        self.contentfunc = contentfunc

    def cache_path(self):
        return os.path.join(abo.config.config().cache_dir_path(), os.path.abspath(self.path).replace('/', '%%'))

    def get(self, force=False):
        cpath = self.cache_path()
        if force or self.mtime(cpath) < self.mtime(self.path):
            try:
                os.makedirs(os.path.dirname(cpath))
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
            content = self.contentfunc()
            pickle.dump(content, file(cpath, 'w'), 2)
            return content
        return pickle.load(file(cpath))

    @staticmethod
    def mtime(path):
        try:
            return os.stat(path).st_mtime
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            return -1

class TransactionCache(FileCache):

    def __init__(self, path, transaction_source):
        super(TransactionCache, self).__init__(path, lambda: transaction_source.transactions())

    def transactions(self, **kwargs):
        return self.get(**kwargs)
