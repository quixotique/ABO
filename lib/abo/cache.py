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
import locale
import re

class Cache(object):

    def __init__(self, config, ident, contentfunc, deppaths=(), force=False):
        self.config = config
        self.ident = ident
        self.cpath = os.path.join(self.config.cache_dir_path(), self.ident.replace('/', '%%'))
        self.ctime = -1 if force else self.mtime(self.cpath)
        self.contentfunc = contentfunc
        self.deppaths = list(deppaths)

    def source_paths(self):
        for path in self.deppaths:
            yield path

    def source_mtime(self):
        return max(self.mtime(path) for path in self.source_paths())

    def is_dirty(self):
        return self.ctime < self.source_mtime()

    def get(self):
        stime = self.source_mtime()
        if self.ctime >= stime:
            try:
                logging.debug("load %r" % self.cpath)
                return pickle.load(open(self.cpath, 'rb'))
            except (pickle.UnpicklingError, UnicodeDecodeError):
                pass
        logging.debug("compile %r" % self.ident)
        try:
            os.makedirs(os.path.dirname(self.cpath))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        content = self.contentfunc()
        pickle.dump(content, open(self.cpath, 'wb'), 2)
        self.ctime = stime
        return content

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
        super(FileCache, self).__init__(config, self.path, contentfunc, [self.path] + list(otherpaths), force=force)

class TransactionCache(FileCache):

    def __init__(self, config, path, transaction_source, otherpaths=(), force=False):
        super(TransactionCache, self).__init__(config, path, lambda: transaction_source.transactions(), otherpaths, force=force)

    def transactions(self):
        return self.get()

_chart_cache = None

def chart_cache(config, opts=None):
    global _chart_cache
    if _chart_cache is None:
        def compile_chart():
            logging.info("compile %r", config.chart_file_path)
            import abo.account
            chart = abo.account.Chart.from_file(open_detect_encoding(config.chart_file_path))
            if chart.has_wild_account():
                for tc in transaction_caches(chart, config, opts):
                    tc.get()
            return chart
        _chart_cache = FileCache(config, config.chart_file_path, compile_chart, config.input_file_paths, force=opts and opts['--force'])
    return _chart_cache

_transaction_caches = None

def transaction_caches(chart, config, opts=None):
    global _transaction_caches
    if _transaction_caches is None:
        import abo.journal
        _transaction_caches = []
        for path in config.input_file_paths:
            _transaction_caches.append(TransactionCache(config, path, abo.journal.Journal(config, open_detect_encoding(path), chart=chart), [config.chart_file_path], force=opts and opts['--force']))
    return _transaction_caches

_regex_encoding = re.compile(r'coding[=:]\s*([-\w.]+)', re.MULTILINE)

def detect_encoding(path, line_count=10):
    r"""Inspect the first few lines of a file, looking for a declared file
    encoding.
    """
    firstlines = []
    with open(path, 'r', encoding='ascii', errors='ignore') as f:
        for line in f:
            firstlines.append(line)
            if len(firstlines) >= line_count:
                break
    m = _regex_encoding.search('\n'.join(firstlines))
    return m.group(1) if m else locale.getlocale()[1] or 'ascii'

def open_detect_encoding(path):
    return open(path, 'r', encoding=detect_encoding(path), errors='strict')