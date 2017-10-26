#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python 3 script template (changeme)
"""

import better_exceptions
from airtight.cli import configure_commandline
from airtight.logging import flog
from csv import DictWriter
import json
import logging
from os import walk
from os.path import abspath, join, realpath
import sys
from textnorm import normalize_space

DEFAULT_LOG_LEVEL = logging.WARNING
OPTIONAL_ARGUMENTS = [
    ['-l', '--loglevel', 'NOTSET',
        'desired logging level (' +
        'case-insensitive string: DEBUG, INFO, WARNING, or ERROR',
        False],
    ['-v', '--verbose', False, 'verbose output (logging level == INFO)',
        False],
    ['-w', '--veryverbose', False,
        'very verbose output (logging level == DEBUG)', False],
    ['-p', '--progress', False, 'indicate progress', False],
    ['-o', '--output', '', 'directory where to write the index', True]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ['specs', str, 'which index to create']
]
PROGRESS_INTERVAL = 1000


def generate_indices(specs, output=None, progress=False, **kwargs):
    indices = {}
    if type(specs) == str:
        specs = [specs]
    for spec in specs:
        indices[spec] = []
    path = abspath(realpath(join('data', 'json')))
    i = 0
    last_i = PROGRESS_INTERVAL
    for dirpath, dirnames, filenames in walk(path):
        for filename in filenames:
            if filename.split('.')[-1] == 'json':
                filepath = join(dirpath, filename)
                with open(filepath, 'r') as f:
                    p = json.load(f)
                i += 1
                for spec in specs:
                    indices[spec].extend(
                        globals()['make_{}'.format(spec)](p))
        if i >= last_i:
            if progress:
                print('progress: {} places processed'.format(i))
                last_i = last_i + PROGRESS_INTERVAL
    idx = indices['names']
    idx = sorted(idx, key=lambda k: ''.join(k['name'].lower().split()))
    if output is None or output == '':
        for e in idx:
            print('{}: {}'.format(e['name'], e['pid']))
    else:
        where = abspath(realpath(output))
        where = join(where, 'names_index.csv')
        with open(where, 'w', encoding='utf-8') as f:
            writer = DictWriter(f, idx[0].keys())
            writer.writeheader()
            i = 0
            for e in idx:
                writer.writerow(e)
                i += 1
        print('wrote header plus {} data rows to {}'.format(i, where))
        where = where.replace('.csv', '.json')
        with open(where, 'w', encoding='utf-8') as f:
            json.dump(idx, f, sort_keys=True, indent=4, ensure_ascii=False)
        print('wrote {} JSON objects to {}'.format(i, where))

def make_names(p):
    names = [p['title']]
    for n in p['names']:
        if n['attested'] is not None and normalize_space(n['attested']) != '':
            names.append(normalize_space(n['attested']))
        rr = [normalize_space(r)
              for r in n['romanized'].split(',')
              if normalize_space(r) != '']
        if len(rr) > 0:
            names.extend(rr)
    names = list(set(names))
    located = bool(len([l for l in p['locations'] if l['geometry'] is not None]))
    precision = [f['properties']['location_precision'] for f in p['features']]
    precise = bool(len([pr for pr in precision if pr == 'precise']))
    uri = p['uri']
    reprPoint = p['reprPoint']
    try:
        longitude = reprPoint[0]
    except TypeError:
        longitude = None
    try:
        latitude = reprPoint[1]
    except TypeError:
        latitude = None
    entries = [
        {
            'name': n,
            'uri': uri,
            'precise': precise,
            'located': located,
            'representative_longitude': longitude,
            'representative_latitude': latitude
        } for n in names]
    return entries





def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    generate_indices(**kwargs)


if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
