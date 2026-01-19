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
import concurrent.futures

class Cache(object):

    def __init__(self, config, opts, ident, deppaths=()):
        self.config = config
        self.opts = opts
        self.ident = ident
        self.cpath = os.path.join(self.config.cache_dir_path, self.ident.replace('/', '%%'))
        self.ctime = -1 if self.opts and self.opts['--force'] else self.mtime(self.cpath)
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
            content = self.make_content()
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

    def __init__(self, config, opts, path, otherpaths=()):
        self.path = os.path.abspath(path)
        super(FileCache, self).__init__(config,
                                        opts,
                                        os.path.relpath(self.path, config.base_dir_path),
                                        [self.path] + list(otherpaths))

class ChartCache(FileCache):

    def __init__(self, config, opts):
        FileCache.__init__(self, config, opts, path=config.chart_file_path, otherpaths=config.journal_file_paths)

    def make_content(self):
        logging.info("compile %r", self.config.chart_file_path)
        import abo.account
        chart = abo.account.Chart.from_file(self.config.open(self.config.chart_file_path))
        if chart.has_wild_account():
            # Iterate over all accounts named in all transactions, in order to
            # instantiate all wild accounts.
            for t in all_transactions(self.config, self.opts):
                for e in t.entries:
                    chart[e.account]
        return chart

_chart = None

def chart(config, opts=None):
    global _chart
    if _chart is None:
        _chart = ChartCache(config, opts).get()
    return _chart

class TransactionCache(FileCache):

    def __init__(self, config, opts, path):
        FileCache.__init__(self, config, opts, path, otherpaths=[config.chart_file_path])

    def make_content(self):
        import abo.journal
        return list(abo.journal.Journal(self.config, self.config.open(self.path), chart=chart(self.config, self.opts)).transactions())

_all_transactions = {}

def all_transactions(config, opts=None):
    global _all_transactions
    key = config.transaction_cache_key()
    transactions = _all_transactions.get(key)
    if transactions is None:
        caches = [TransactionCache(config, opts, path) for path in config.journal_file_paths]
        with concurrent.futures.ProcessPoolExecutor() as executor:
            transactions = []
            for t in executor.map(Cache.get, caches):
                transactions += t
        logging.debug(f"cache {len(transactions)} transactions")
        _all_transactions[key] = transactions
    return transactions
