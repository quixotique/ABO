#!/usr/bin/env python3

import sys
import csv
import re
from collections import namedtuple

def reader(f):
    reader = csv.reader(f)
    Row = namedtuple('Row', map(to_attribute_name, next(reader)))
    for row in reader:
        yield Row._make(map(str.strip, row))

e = 0
def to_attribute_name(s):
    if s:
        s = re.sub(r'\(.*\)', '', s)
        s = s.strip()
        s = s.lower()
        s = re.sub(r'\W+', '_', s)
        return s
    global e
    e += 1
    return 'empty_' + str(e)

def main():
    for row in reader(open(sys.argv[1], newline='')):
        print(repr(row))

if __name__ == '__main__':
    main()
