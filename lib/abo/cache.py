# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2013 Andrew Bettison

"""Transaction cache.
"""

import logging
import os
import os.path
import errno
import pickle

class Cache(object):

    def __init__(self, config, ident, contentfunc, deppaths=(), force=False):
        self.config = config
        self.ident = ident
        self.cpath = os.path.join(self.config.cache_dir_path, self.ident.replace('/', '%%'))
        self.ctime = -1 if force else self.mtime(self.cpath)
        self.contentfunc = contentfunc
        self.deppaths = list(deppaths)
        self.content = None

    def source_paths(self):
        for path in self.deppaths:
            yield path

    def source_mtime(self):
        return max(self.mtime(path) for path in self.source_paths())

    def is_dirty(self):
        return self.ctime < self.source_mtime()

    def get(self):
        if self.is_dirty():
            logging.debug("compile %r" % self.ident)
            try:
                os.makedirs(os.path.dirname(self.cpath))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            content = self.contentfunc()
            pickle.dump(content, open(self.cpath, 'wb'), 2)
            self.ctime = self.mtime(self.cpath)
            self.content = content
        elif self.content is None:
            try:
                logging.debug("load %r" % self.cpath)
                self.content = pickle.load(open(self.cpath, 'rb'))
            except (pickle.UnpicklingError, UnicodeDecodeError):
                pass
        return self.content

    @staticmethod
    def mtime(path):
        try:
            return os.stat(path).st_mtime
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            return -1

class FileCache(Cache):

    def __init__(self, config, path, contentfunc, otherpaths=(), force=False):
        self.path = os.path.abspath(path)
        super(FileCache, self).__init__(config,
                                        os.path.relpath(self.path, config.base_dir_path),
                                        contentfunc,
                                        [self.path] + list(otherpaths),
                                        force=force)

class TransactionCache(FileCache):

    def __init__(self, config, path, transaction_iterable, otherpaths=(), force=False):
        super(TransactionCache, self).__init__(config, path, lambda: list(transaction_iterable), otherpaths, force=force)

    def transactions(self):
        return self.get()

_chart_cache = None

def chart_cache(config, opts=None):
    global _chart_cache
    if _chart_cache is None:
        def compile_chart():
            logging.info("compile %r", config.chart_file_path)
            import abo.account
            chart = abo.account.Chart.from_file(config.open(config.chart_file_path))
            if chart.has_wild_account():
                # Iterate over all accounts named in all transactions, in order to
                # instantiate all wild accounts.
                for tc in transaction_caches(chart, config, opts):
                    for t in tc.transactions():
                        for e in t.entries:
                            chart[e.account]
            return chart
        _chart_cache = FileCache(config, config.chart_file_path, compile_chart, config.journal_file_paths, force=opts and opts['--force'])
    return _chart_cache

_transaction_caches = None

def transaction_caches(chart, config, opts=None):
    global _transaction_caches
    if _transaction_caches is None:
        import abo.journal
        logging.debug("populate transaction caches")
        _transaction_caches = []
        for path in config.journal_file_paths:
            _transaction_caches.append(
                    TransactionCache(
                            config,
                            path,
                            abo.journal.Journal(config, config.open(path), chart=chart).transactions(),
                            [config.chart_file_path],
                            force=opts and opts['--force']
                        )
                )
    return _transaction_caches
