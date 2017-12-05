#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report most recent changes
"""

import better_exceptions
from airtight.cli import configure_commandline
from airtight.logging import flog
from bs4 import BeautifulSoup as bs
from collections import OrderedDict
import datetime
from dateutil import parser as date_parser
from dateutil import tz
import json
import logging
from lxml import etree
from pyatom import AtomFeed
import requests
import requests_cache
from os import walk
from os.path import abspath, join, realpath
from pprint import pformat, pprint
from slugify import slugify
import sys
from textnorm import normalize_space, normalize_unicode

requests_cache.install_cache('recent_cache')
json_cache = {}  # keep place info in memory in case we need it

# the following hacktastical datetime nonsense is brought to you by Python's
# naive vs. timezone-aware datetime mess, which hopefully someday will go the
# way of non-unicode vs. unicode strings
UTC = tz.gettz('UTC')
today = datetime.datetime.combine(
    datetime.date.today(),
    datetime.time(0, tzinfo=UTC))
last_sunday = today - datetime.timedelta(7 + ((today.weekday() + 1) % 7))
default_since = last_sunday.isoformat()
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
    ['-c', '--count', '-1', 'how many places to report', False],
    ['-s', '--since', default_since, 'date since to report', False],
    ['-a', '--atom', 'NOTSET', 'path to atom file', False],
    ['-b', '--blog', 'NOTSET', 'path to html file', False]
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ['path', str, 'path to json directory']
]

IGNORE = [
    'Baseline created',
    'check in of working copy'
    ]
FEED_BODY_TEMPLATE = """
<p>
    <a href="{user_url}">{user_fullname}</a>
    {action_verb}
    {resource_type} Resource
    <a href="{resource_url}>{resource_id}: {resource_title}</a>
</p>
"""
PLAIN_BODY_TEMPLATE = """
{user_fullname} {action_verb} {resource_type} Resource
{resource_id}: {resource_title}
"""
USER_SUBSTITUTIONS = {
    'admin': 'thomase'
}
USER_URL_TEMPLATE = 'https://pleiades.stoa.org/author/{}'
PLACE_URL_TEMPLATE = 'https://pleiades.stoa.org/places/{}'
VERBS = {
    'Edited': 'made general edits',
    'references': 'edited references',
    'summary': 'edited summary',
    'description': 'edited summary',
    'reference': 'added a reference',
    'Initial revision': 'made general edits'
}

def purge_json_cache(exceptions: list, verbose=False, **kwargs):
    global json_cache
    if verbose: print('purging json_cache of unneeded place info ...')
    keys = [k for k in json_cache.keys() if k not in exceptions]
    for k in keys:
        del json_cache[k]
    if verbose: print('... purged {} unneeded places'.format(len(keys)))

def norm(v: str):
    return normalize_space(normalize_unicode(v))

def make_verb(event: dict):
    shorthand = [
        'references'
    ]
    if event['new']:
        verb = 'created a new'
    else:
        comment = event['comment']
        if comment == 'Edited':
            verb = 'made general edits to'
        elif comment in shorthand:
            verb = 'modified ' + comment + ' on '
        elif comment.startswith('PleiadesRefBot cleaned up '):
            verb = comment.replace(
                'PleiadesRefBot cleaned up ',
                'used PleiadesRefBot to clean up ') + ' on '
        else:
            verb = 'changed ' + comment + ' on '
    return verb

def make_atom(
    actions: list,
    users: dict,
    feed_title='Pleiades Updates',
    feed_url='https://pleiades.stoa.org/news/updates/atom',
    feed_username='thomase',
    feed_file_path=None
    ):

    feed = AtomFeed(
        title=feed_title,
        feed_url=feed_url,
        author=users[feed_username]['user_fullname']
        )

    for action in actions:
        username = action['modifiedBy']
        try:
            username = USER_SUBSTITUTIONS[username]
        except KeyError:
            pass
        user = users[username]
        body_args = user.copy()
        body_args.update(action)
        feed_body = FEED_BODY_TEMPLATE.format(**body_args)
        feed.add(
            title=action['resource_title'],
            content=feed_body,
            author=user['user_fullname'],
            url=action['resource_url'],
            updated=date_parser.parse(action['modified'])
            )
        print(norm(PLAIN_BODY_TEMPLATE.format(**body_args)))
    return feed

def make_blog_post(
    events: list,
    blog: str,
    verbose=False,
    **kwargs
    ):

    if blog == 'NOTSET':
        if verbose: print('Skipped blog creation per commandline.')
        return
    soup = bs('<div></div>', 'lxml')
    blog_serialize_actions(soup, 'created', events['creations'])
    blog_serialize_actions(soup, 'changed', events['changes'])
    path = abspath(realpath(blog))
    html = soup.prettify("utf-8")
    with open(path, 'wb') as f:
        f.write(html)

    print('wrote blog post on {}'.format(path))

def blog_serialize_actions(soup, verb, actions):
    sorted_actions = sorted(
        actions,
        key=lambda a:
            a['user_fullname'].split()[-1].lower() +
            ''.join(a['user_fullname'].split()[0:-1]).lower() +
            ''.join(a['resource_title'].split()).lower()
            )
    previous_name = ''
    for a in sorted_actions:
        name = a['user_fullname']
        if name != previous_name:
            slug = slugify(
                name, max_length=40, word_boundary=True, separator='_',
                save_order=True)
            div_tag = soup.new_tag('div', id='{}_by_{}'.format(verb, slug))
            soup.div.append(div_tag)
            h3_tag = soup.new_tag('h3')
            div_tag.append(h3_tag)
            link_tag = soup.new_tag('a', href=a['user_url'])
            h3_tag.append(link_tag)
            link_tag.append(name)
            h3_tag.append(' {} the Following Place Resources:'.format(verb.capitalize()))
            list_tag = soup.new_tag('ul')
            div_tag.append(list_tag)
        item_tag = soup.new_tag('li')
        list_tag.append(item_tag)
        link_tag = soup.new_tag('a', href=a['resource_url'])
        item_tag.append(link_tag)
        link_tag.append('{} ({})'.format(
            a['resource_title'], a['resource_id']))
        item_tag.append(soup.new_tag('br'))
        if verb == 'changed':
            item_tag.append(a['comment'])
        previous_name = name


def get_user(username: str, users: dict):
    try:
        uname = USER_SUBSTITUTIONS[username]
    except KeyError:
        return users[username]
    else:
        return users[uname]

def get_user_info(
    usernames: list,
    user_substitutions=USER_SUBSTITUTIONS,
    verbose=False,
    veryverbose = False,
    **kwargs):

    if verbose: print(
        'Looking up full names for the {} users responsible for these events'
        ''.format(len(usernames)))
    users = {}
    for username in usernames:
        user = {}
        try:
            user_key = user_substitutions[username]
        except KeyError:
            user_key = username
        finally:
            user['username'] = user_key
            user['user_url'] = USER_URL_TEMPLATE.format(user_key)
            users[user_key] = user
        url = user['user_url']
        r = requests.get(url)
        if r.status_code != 200:
            msg = 'Got status {} trying to get {}'.format(r.status_code, url)
            raise RuntimeError(msg)
        else:
            soup = bs(r.text, 'lxml')
            h1 = soup.find('h1')
            user['user_fullname'] = norm(h1.text)
            if veryverbose: print(
                '\tGot full name "{}" for username "{}"'
                ''.format(user['user_fullname'], username))
    if verbose: print('... done')
    return users

def get_history_from_json(path: str, verbose=False, **kwargs):
    global json_cache

    path = abspath(realpath(path))
    history = {}
    p = None
    total_events = 0
    total_places = 0
    if verbose:
        print('parsing histories from Pleiades JSON ...')
    for dirpath, dirnames, filenames in walk(path):
        for filename in filenames:
            if filename.split('.')[-1] == 'json':
                if p:
                    del p
                filepath = join(dirpath, filename)
                with open(filepath, 'r') as f:
                    p = json.load(f)
                del f
                total_places += 1
                pid = p['id']
                json_cache[pid] = p
                history[pid] = p['history']  # unsorted
                log_length = len(history[pid])
                total_events += log_length
    # what about subordinate names, locations, and connections?
    if verbose:
        print(
            '... parsed {} events from {} places'
            ''.format(total_events, total_places))
    return (total_events, total_places, history)

def filter_history(history: dict, ignore=IGNORE, verbose=False, **kwargs):
    total_events = 0
    total_places = 0
    if verbose:
        print(
            'filtering histories to exclude events with the following '
            'comments: ' + str(ignore))
    filtered = {}
    for pid, log in history.items():
        total_places += 1
        filtered_log = filter_log(log, **kwargs)
        if len(filtered_log) > 0:
            filtered[pid] = filtered_log
        total_events += len(filtered[pid])
    if verbose:
        print(
            '... after filtering, there remain {} events from {} places'
            ''.format(total_events, total_places))
    return (total_events, total_places, filtered)

def filter_log(
    log: list,
    ignore=IGNORE,
    verbose=False,
    veryverbose=False,
    **kwargs):
    filtered_log = [e for e in log if e['comment'] not in IGNORE]
    return filtered_log

def determine_most_recent_events(history: dict, verbose=False, **kwargs):
    total_events = 0
    total_places = 0
    events = []
    if verbose:
        print('selecting most recent event from each log...')
    for pid, log in history.items():
        total_places += 1
        sorted_log = sorted(
            log, key=lambda event: event['modified'], reverse=True)
        event = sorted_log[0].copy()
        event['pid'] = pid
        events.append(event)
    total_events = len(events)
    if verbose:
        print(
            '... now we have {} events from {} places'
            ''.format(total_events, total_places))
    if total_events != total_places:
        raise RuntimeError('This aggression must not stand, man.')
    return (total_events, total_places, events)


def sort_and_truncate(
    events: list,
    count: str,  # string representation of integer
    since: str,  # ISO datetime expression
    verbose=False,
    veryverbose=False,
    **kwargs):

    maximum = int(count)
    horizon = date_parser.parse(since).replace(tzinfo=UTC)
    if verbose: print('sorting list of most recent events ...')
    events = sorted(events, key=lambda e: e['modified'], reverse=True)
    if verbose: print('... done')

    if maximum != -1:
        maximum = min(maximum, len(events))
        events = events[:maximum]
        if verbose:
            print(
                'truncated list of recent events to {} per command line '
                'directive'.format(maximum))
    else:
        if verbose: print(
            'truncating recent events list to items since {} ...'
            ''.format(horizon.isoformat()))
        temp = []
        for e in events:
            if date_parser.parse(e['modified']) >= horizon:
                temp.append(e)
            else:
                break
        events = temp
        del temp
        if verbose: print(
            '... truncated to a total of {} events'.format(len(events)))
    total_events = len(events)
    pids = sorted(list(set([e['pid'] for e in events])), key=lambda pid: int(pid))
    purge_json_cache(exceptions=pids, verbose=verbose, **kwargs)
    total_places = len(pids)
    if veryverbose:
        print('pids:')
        pprint(pids, indent=4)
    if verbose: print(
        'Now we have {} events from {} places'
            ''.format(total_events, total_places))
    return (total_events, total_places, events)

def normalize_events(events: list, users: dict, verbs=VERBS, verbose=False, **kwargs):
    global json_cache
    if verbose: print('normalizing events ...')
    for e in events:
        pid = e['pid']
        resource = json_cache[pid]
        e['resource_id'] = resource['id']
        e['resource_url'] = PLACE_URL_TEMPLATE.format(resource['id'])
        e['resource_title'] = resource['title']
        if len(filter_log(resource['history'])) == 1:
            e['new'] = True
        else:
            e['new'] = False
        comment = norm(e['comment'])
        try:
            comment = verbs[comment]
        except KeyError:
            if comment.startswith('PleiadesRefBot cleaned'):
                comment = comment.replace(
                    'PleiadesRefBot cleaned',
                    'used PleiadesRefBot to clean')
        e['comment'] = comment
        username = e['modifiedBy']
        e.update(get_user(username, users))

    if verbose: print('... done')
    return events

def categorize(events: list, verbose=False, **kwargs):
    if verbose: print('Categorizing events ...')
    creations = [e for e in events if e['new'] == True]
    changes = [e for e in events if e not in creations]
    if verbose: print(
        '... categorized {} creation events and {} change events'
        ''.format(len(creations), len(changes)))
    return {
        'creations': creations,
        'changes': changes
    }

def dump_events(events: list, verbose=False, veryverbose=False, **kwargs):
    if veryverbose or verbose:
        for k, v in events.items():
            for e in v:
                if veryverbose:
                    pprint(e, indent=4)
                elif verbose:
                    print('{resource_title}: {user_fullname} {comment}'.format(**e))

def main(**kwargs):
    """
    main function
    """
    logger = logging.getLogger(sys._getframe().f_code.co_name)
    logger.debug('kwargs: {}'.format(pformat(kwargs)))


    verbose = kwargs['verbose']
    event_count, place_count, history = get_history_from_json(**kwargs)
    event_count, place_count, history = filter_history(history, **kwargs)
    event_count, place_count, events = determine_most_recent_events(history,
        **kwargs)
    event_count, place_count, events = sort_and_truncate(events, **kwargs)
    usernames = list(set([e['modifiedBy'] for e in events]))
    users = get_user_info(usernames, **kwargs)
    events = normalize_events(events, users, **kwargs)
    events = categorize(events, **kwargs)
    dump_events(events, **kwargs)
    make_blog_post(events, **kwargs)
    sys.exit()

    for event in events:
        event['action_verb'] = make_verb(event)

    if kwargs['atom'] != 'NOTSET':
        feed = make_atom(events, users)
        path = abspath(realpath(kwargs['atom']))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(feed.to_string())
    #if kwargs['blog'] != 'NOTSET':
    #    make_blog_post(kwargs['blog'], events, users)
    sys.exit()
    for username, fullname in users.items():
        print(fullname)
        actions = [e for e in events if e['modifiedBy'] == username]
        creations = [a for a in actions if a['new'] == True]
        if len(creations) > 0:
            print('\tNew Place{}:'.format(['', 's'][len(creations) > 1]))
            for action in creations:
                print('\t\t{pid}'.format(**action))  # need to fetch detail from json
        actions = [a for a in actions if a not in creations]
        if len(actions) > 0:
            print('\tUpdated Place{}:'.format(['', 's'][len(actions) > 1]))
            for action in actions:
                print('\t\t{pid}'.format(**action))  # need to fetch detail from json







if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
