# vim: sw=4 sts=4 et fileencoding=utf8 nomod
#
# Copyright 2020 Andrew Bettison

if __name__ == '__main__':
    import sys
    if sys.path[0] == sys.path[1] + '/abo':
        del sys.path[0]
    import doctest
    import abo.email.folder
    doctest.testmod(abo.email.folder)

import sys
import re
import fnmatch
import collections

class Filer(object):

    Folder = collections.namedtuple('Folder', ['name', 'is_list', 'is_self'])

    _re_line = re.compile(r'\s*([*!]?)\s*([A-Za-z0-9_.-]+)\s*:(.*?)(?:;(.*))?')

    def __init__(self, text):
        r"""Parse the given text as configuration that maps email addresses to folders.

            >>> Filer('some1@gmail.com')
            Traceback (most recent call last):
            ValueError: line 1: malformed

            >>> Filer('\n\n: some1@gmail.com')
            Traceback (most recent call last):
            ValueError: line 3: malformed

            >>> Filer('one: some{1@gmail.com')
            Traceback (most recent call last):
            ValueError: line 1: malformed pattern: some{1@gmail.com

        """
        self.map = []
        self.folder_by_name = dict()
        for num, line in enumerate(text.splitlines(), 1):
            try:
                if not line or line.isspace() or line.startswith('#'): continue
                m = self._re_line.fullmatch(line)
                if not m:
                    raise ValueError('malformed')
                #print(m.groups(), file=sys.stderr)
                flag, folder_name, patterns, subject = m.groups()
                is_self = flag == '!'
                is_list = flag == '*'
                subject_rexp = self.pattern_to_regex(subject.strip()) if subject else None
                folder = self.folder_by_name.get(folder_name)
                if folder is None:
                    pass
                elif folder.is_self != is_self:
                    raise ValueError('inconsistent self')
                else:
                    is_list = folder.is_list or is_list
                folder = self.Folder(name=folder_name, is_list=is_list, is_self=is_self)
                self.folder_by_name[folder_name] = folder
                for pattern in patterns.split():
                    self.map.append((self.pattern_to_regex(pattern), subject_rexp, folder))
            except ValueError as e:
                raise ValueError(f'line {num}: {e}')

    @staticmethod
    def pattern_to_regex(pattern):
        regex = ''.join('@(?:.*\.)?' if s in ('@', '@*.') else '(?:' if s == '{' else ')' if s == '}' else '|' if s == ',' else fnmatch.translate(s).replace('\Z', '') if s else '' for s in re.split(r'(@\*\.|[@{,}])', pattern))
        #print(regex, file=sys.stderr)
        try:
            return re.compile(regex, re.IGNORECASE)
        except:
            raise ValueError(f'malformed pattern: {pattern}')

    def lookup_address(self, address, subject=None):
        r"""Return the first folder that matches a given email address and optionally subject, or
        None if no folder matches.

            >>> f = Filer(text='!one  : some1@gmail.com\n two: *@two.org ; WAH  \n* list:  {a,b}@*.list.org')
            >>> f.lookup_address('some1@sub.gmail.com').name
            'one'
            >>> f.lookup_address('some1@sub.gmail.com').is_self
            True
            >>> f.lookup_address('some2@sub.gmail.com') is None
            True
            >>> f.lookup_address('them@two.org').name
            'two'
            >>> f.lookup_address('us@two.org', subject='Nothing') is None
            True
            >>> f.lookup_address('us@two.org', subject='WAH at start')
            Folder(name='two', is_list=False, is_self=False)
            >>> f.lookup_address('us@two.org', subject='ends with WAH') is None
            True

        """
        for address_rexp, subject_rexp, folder in self.map:
            if address_rexp.fullmatch(address) and (subject_rexp is None or subject is None or subject_rexp.match(subject)):
                return folder
        return None

    def lookup_message(self, from_address, sender_address=None, to_addresses=(), subject=None):
        r"""Return a set of folders in which to save a given email message.

            >>> f = Filer(text='!one  : some1@gmail.com\n two: *@two.org ; WAH  \n* list:  {a,b}@*.list.org')
            >>> f.lookup_message('us@two.org')
            {Folder(name='two', is_list=False, is_self=False)}
            >>> f.lookup_message('us@two.org', subject='Nothing')
            set()
            >>> f.lookup_message('us@two.org', subject='WAH at start')
            {Folder(name='two', is_list=False, is_self=False)}
            >>> f.lookup_message('us@two.org', subject='ends with WAH')
            set()
            >>> f.lookup_message('a@list.org')
            {Folder(name='list', is_list=True, is_self=False)}

        """
        # Look up the sender using the 'From:' header, and if they have no
        # folder, then the 'Sender:' header.
        from_folder = self.lookup_address(from_address, subject=subject)
        if not from_folder and sender_address:
            from_folder = self.lookup_address(sender_address, subject=subject)
        # Look up the folders for all recipients, including self.
        to_folders = set()
        folder_self = None
        for to_address in to_addresses:
            to_folder = self.lookup_address(to_address, subject=subject)
            if not to_folder: continue
            if not to_folder.is_self:
                to_folders.add(to_folder)
            elif not folder_self:
                folder_self = to_folder
        # If the sender has no folder, then use the list folders of the recipients.
        if not from_folder:
            return set(f for f in to_folders if f.is_list)
        # If the sender is recognised and is not self, then file under the sender's folder.
        if not from_folder.is_self:
            return set([from_folder])
        # Otherwise, sender is self, so use all recipient folder(s) if there are any.
        if to_folders:
            return to_folders
        # Otherwise, use self folder if sender or recipient is self.
        if folder_self:
            return set(folder_self)
        # Otherwise, no luck.
        return set()
