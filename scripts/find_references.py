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
    ['-m', '--mode', 'contains', 'matching mode', True],
    ['-s', '--case_sensitive', False, 'True or False', False],
    ['-o', '--output', '', 'where to output CSV of results', True]
    ['-a', '--access_uri', '*', 'access uri', False],
    ['-b', '--bibliographic_uri', '*', 'bibliographic uri', False],
    ['-t', '--short_title', '*', 'short_title'], False]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]

def _sensitize(v, sensitive):
    if sensitive:
        return v
    else:
        return v.lower()

def _dispatch(obj, value, case_sensitive, func, **kwargs):
    first, *rest = field.split('/')
    child = obj[first]
    if type(child) == dict:
        path = '/'.join(rest)
        results = globals()[func](child, path, value, case_sensitive)
        for r in results:
            r['path'] = '/'.join(first, r['path'])
        return results
    elif type(child) == list:
        if len(child) == 0:
            # print('child 0')
            return []
        else:
            # print('substantive child')
            path = '/'.join(rest[1:])
            if rest[0] != '?':
                # print('not question mark')
                i = int(rest[0])
                results = globals()[func](child[i], path, value, case_sensitive)
                # print ('not question mark results: {}'.format(len(results)))
                for r in results:
                    r['path'] = '/'.join(first, r['path'])
            else:
                # print('question mark')
                results = []
                for i, c in enumerate(child):
                    rr = globals()[func](c, path, value, case_sensitive)
                    # print('quesiton mark results: {}'.format(len(results)))
                    for r in rr:
                        r['path'] = '/'.join((first, '{}'.format(i), r['path']))
                    results.extend(rr)
            return results


def _contains(reference, **kwargs):
    cs = kwargs['case_sensitive']
    au = _sensitize(kwargs['access_uri'], cs)
    st = kwargs['short_title']
    if au == '*' or au in _sensitize(reference['access_uri'], cs):
        bu = _sensitize(kwargs['bibliographic_uri'], cs)

    # print('quarry: {}'.format(quarry))
    # print('target: {}'.format(target))
    if target in quarry:
        d = {
            'path': field,
            'value': value,
            'match': obj[field],
            'sensitive': case_sensitive
        }
        # print('boom')
        return [d]
    else:
        return []

def _startswith(obj, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_startswith')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry.startswith(target):
        d = {
            'path': field,
            'value': value,
            'match': obj[field],
            'sensitive': case_sensitive
        }
        return [d]
    else:
        return []

def _endswith(obj, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_endswith')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry.endswith(target):
        d = {
            'path': field,
            'value': value,
            'match': obj[field],
            'sensitive': case_sensitive
        }
        return [d]
    else:
        return []

def _exact(obj, value, case_sensitive, **kwargs):
    if '/' in field:
        return _dispatch(obj, field, value, case_sensitive, '_exact')
    quarry = _sensitize(obj[field], case_sensitive)
    target = _sensitize(value, case_sensitive)
    if quarry == target:
        d = {
            'path': field,
            'value': value,
            'match': obj[field],
            'sensitive': case_sensitive
        }
        return [d]
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
                for reference in p['references']:
                    results = globals()['_{}'.format(kwargs['mode'])](reference, **kwargs)
                if results is not None:
                    for r in results:
                        r['place_uri'] = p['uri']
                    hits.extend(results)
                # handle references on names, locations, and connections
            # print('hits: {}'.format(len(hits)))
            # sys.exit(0)
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
