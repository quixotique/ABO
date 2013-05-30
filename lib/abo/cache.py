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

    def __init__(self, config, path, contentfunc, otherpaths=(), force=False):
        self.config = config
        self.path = path
        self.cpath = self.cache_path(path)
        self.ctime = -1 if force else self.mtime(self.cpath)
        self.contentfunc = contentfunc
        self.otherpaths = list(otherpaths)

    def source_paths(self):
        yield self.path
        for path in self.otherpaths:
            yield path

    def source_mtime(self):
        return max(self.mtime(path) for path in self.source_paths())

    def is_dirty(self):
        return self.ctime < self.source_mtime()

    def get(self):
        stime = self.source_mtime()
        if self.ctime < stime:
            import sys
            print >>sys.stderr, "compile %r" % self.path
            try:
                os.makedirs(os.path.dirname(self.cpath))
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
            content = self.contentfunc()
            pickle.dump(content, file(self.cpath, 'w'), 2)
            self.ctime = stime
            return content
        return pickle.load(file(self.cpath))

    def cache_path(self, path):
        return os.path.join(self.config.cache_dir_path(), os.path.abspath(path).replace('/', '%%'))

    @staticmethod
    def mtime(path):
        try:
            return os.stat(path).st_mtime
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            return -1

class TransactionCache(FileCache):

    def __init__(self, config, path, transaction_source, otherpaths=(), force=False):
        super(TransactionCache, self).__init__(config, path, lambda: transaction_source.transactions(), otherpaths, force=force)

    def transactions(self):
        return self.get()
