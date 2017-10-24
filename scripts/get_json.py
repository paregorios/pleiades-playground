#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python 3 script template (changeme)
"""

from airtight.cli import configure_commandline
from airtight.logging import flog
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date
import gzip
import json
import logging
from os import makedirs
from os.path import abspath, dirname, getmtime, join, realpath
import requests

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
    ['-u', '--user_agent', 'Pleiades Playground 0.1', 'user agent for header',
        False],
    ['-f', '--from', '', 'email address', False]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    headers = {
        'User-Agent': kwargs['user_agent']
    }
    if kwargs['from'] != '':
        headers['From'] = kwargs['from']
    url = ('http://atlantides.org/downloads/pleiades/json/'
           'pleiades-places-latest.json.gz')
    local_filename = url.split('/')[-1]
    path = join('data', local_filename)
    modified = datetime.fromtimestamp(getmtime(path), timezone.utc)
    if modified.date() < datetime.today().date():
        r = requests.get(url, stream=True)
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
        print('downloaded {}'.format(path))
    else:
        print("already have today's version of {}".format(path))
    with gzip.open(path, 'rb') as f:
        j = json.load(f)
    places = j['@graph']
    del(j)
    print('There are {} places in this file.'.format(len(places)))
    total = len(places)
    for i, p in enumerate(places):
        if (i % 1000 == 0):
            print('percent complete: {}'.format(int(i/total * 100.)))
        pid = p['id']
        parts = list(pid)
        parts = parts[0:len(parts)-2]
        parts.insert(0, 'json')
        parts.insert(0, 'data')
        parts.append(pid)
        path = '{}.json'.format(join(*parts))
        path = abspath(realpath(path))
        save = False
        try:
            file_modified = datetime.fromtimestamp(getmtime(path), timezone.utc)
        except FileNotFoundError:
            save = True
        else:
            place_modified = sorted([parse_date(h['modified']) for h in p['history']])[-1]
            if file_modified < place_modified:
                save = True
        if save:
            makedirs(dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(p, f, sort_keys=True, indent=4, ensure_ascii=False)

        #


if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
