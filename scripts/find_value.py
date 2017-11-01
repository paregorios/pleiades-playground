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
from jsonpath_ng import parse
import logging
from os import walk
from os.path import abspath, join, realpath
from pprint import pprint
import sys

MODES = [
    'contains',
    'startswith',
    'endswith',
    'equals'
]
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
    ['-j', '--jsonpath', '', 'a jsonpath expression', True],
    ['-o', '--output', '', 'where to output CSV of results', False],
    ['-m', '--mode', 'contains', 'matching mode; one of : {}'.format(MODES), True],
    ['-t', '--target_value', '', 'value to match', True],
    ['-s', '--case_sensitive', False, 'should matches be case-sensitive', False]

]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]

def _lower(v, s):
    if s:
        return v
    else:
        return v.lower()


def _sensitize(**kwargs):
    return (
        _lower(getattr(kwargs['candidate'], 'value'), kwargs['case_sensitive']),
        _lower(kwargs['target_value'], kwargs['case_sensitive'])
        )


def _contains(**kwargs):
    quarry, target = _sensitize(**kwargs)
    if target in quarry:
        return [kwargs['candidate']]
    else:
        return []


def _startswith(**kwargs):
    quarry, target = _sensitize(**kwargs)
    if quarry.startswith(target):
        return [kwargs['candidate']]
    else:
        return []


def _endswith(obj, field, value, case_sensitive, **kwargs):
    quarry, target = _sensitize(**kwargs)
    if quarry.endswith(target):
        return [kwargs['candidate']]
    else:
        return []


def _exact(obj, field, value, case_sensitive, **kwargs):
    quarry, target = _sensitize(**kwargs)
    if quarry == target:
        return [kwargs['candidate']]
    else:
        return []


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    path = abspath(realpath(join('data', 'json')))
    jrx = parse(kwargs['jsonpath'])
    hits = {}
    files = 0
    for dirpath, dirnames, filenames in walk(path):
        for filename in filenames:
            if filename.split('.')[-1] == 'json':
                filepath = join(dirpath, filename)
                with open(filepath, 'r') as f:
                    p = json.load(f)
                files += 1
                candidates = jrx.find(p)
                matches = []
                for c in candidates:
                    matches = globals()['_{}'.format(kwargs['mode'])](candidate=c, **kwargs)
                pid = p['uri'].split('/')[-1]
                for m in matches:
                    try:
                        hits[pid].append(m)
                    except KeyError:
                        hits[pid] = [m]
                if files % 1000 == 0:
                    print(
                        'Checked {} files. {} matches so far.'
                        ''.format(files, len(hits)))
    if kwargs['output'] != '':
        if len(hits) == 0:
            print('No results found.')
        else:
            where = abspath(realpath(kwargs['output']))
            if not(where.endswith('.json')):
                where = join(where, 'found_values.json')
            with open (where, 'w', encoding="utf-8") as f:
                json.dump(hits, f, indent=4, sort_keys=True, ensure_ascii=False)
            print('wrote {} results to {}'.format(len(hits), filepath))
    else:
        print('{} hits'.format(len(hits)))
        for pid, matches in hits.items():
            for match in matches:
                print('{}[{}]: "{}"'.format(pid, match.full_path, match.value))


if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
