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
from pprint import pprint
import sys

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
    ['-f', '--field', '', 'what field', True],
    ['-x', '--value', '', 'directory where to write the index', True],
    ['-m', '--mode', 'contains', 'matching mode', True],
    ['-s', '--case_sensitive', False, 'True or False', False],
    ['-o', '--output', '', 'where to output CSV of results', True]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]

def _sensitize(v, sensitive):
    if sensitive:
        return v
    else:
        return v.lower()

def _dispatch(obj, field, value, case_sensitive, func):
    first, *rest = field.split('/')
    child = obj[first]
    if type(child) == dict:
        path = '/'.join(rest)
        results = globals()[func](child, path, value, case_sensitive)
        for r in results:
            r['path'] = '/'.join(first, r['path'])
    elif type(child) == list:
        if len(child) == 0:
            return []
        else:
            path = '/'.join(rest[1:])
            if rest[0] != '?':
                i = int(rest[0])
                results = globals()[func](child[i], path, value, case_sensitive)
                for r in results:
                    r['path'] = '/'.join(first, r['path'])
            else:
                results = []
                for i, c in enumerate(child):
                    rr = (globals()[func](c, path, value, case_sensitive))
                    for r in rr:
                        r['path'] = '/'.join((first, '{}'.format(i), r['path']))


def _contains(obj, field, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_contains')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if target in quarry:
        d = {
            'path': field,
            'value': value,
            'match': obj[field],
            'sensitive': case_sensitive
        }
        return [d]
    else:
        return []

def _startswith(obj, field, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_startswith')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry.startswith(target):
        return [obj[field]]
    else:
        return []

def _endswith(obj, field, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_endswith')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry.endswith(target):
        return [obj[field]]
    else:
        return []

def _exact(obj, field, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_exact')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry == target:
        return [obj[field]]
    else:
        return []

def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    path = abspath(realpath(join('data', 'json')))
    hits = []
    for dirpath, dirnames, filenames in walk(path):
        for filename in filenames:
            if filename.split('.')[-1] == 'json':
                filepath = join(dirpath, filename)
                with open(filepath, 'r') as f:
                    p = json.load(f)
                results = globals()['_{}'.format(kwargs['mode'])](p, **kwargs)
                if results is not None:
                    for r in results:
                        r['place_uri'] = p['uri']
                    if kwargs['output'] == '':
                        for r in results:
                            print('{')
                            for k,v in r.items():
                                print("\t'{}': '{}'".format(k, v))
                            print('}')
                    else:
                        hits.extend(results)
    if kwargs['output'] != '':
        if len(hits) == 0:
            print('No results found.')
        else:
            where = abspath(realpath(kwargs['output']))
            filepath = join(where, 'found_values.json')
            with open (filepath, 'w', encoding="utf-8") as f:
                json.dump(hits, f, indent=4, sort_keys=True, ensure_ascii=False)
            print('wrote {} results to {}'.format(len(hits), filepath))

if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
