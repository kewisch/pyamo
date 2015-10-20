#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import os
import shutil
import sys
import time

import getpass
import logging
import subprocess
import tempfile
import httplib

from arghandler import subcmd, ArgumentHandler
from .service import AddonsService
from .utils import RE_VERSION_BETA

DEFAULT_MESSAGE = {
    'public': 'Your add-on submission has been approved.',
    'prelim': 'Your add-on submission has been approved.',
    'reject': 'Your version was rejected because of the following problems:',
    'info': 'Please provide us with detailed information on how to test your add-on.',
    'super': 'halp!',
    'comment': 'FYI: bananas!'
}

QUEUES = {
    'unlisted/nominated': 'unlisted_queue/nominated',
    'unlisted/pending': 'unlisted_queue/pending',
    'unlisted/preliminary': 'unlisted_queue/preliminary',
    'fast': 'queue/fast',
    'nominated': 'queue/nominated',
    'pending': 'queue/pending',
    'preliminary': 'queue/preliminary',
    'reviews': 'queue/reviews'
}
ALL_QUEUES = QUEUES.copy()
ALL_QUEUES.update({v: v for v in QUEUES.values()})
DEFAULT_QUEUE = 'nominated'

LOG_SORTKEYS = [
    'date', 'addonname', 'version', 'reviewer', 'action'
]

REVIEW_LOGS = ['reviewlog', 'logs', 'beta_signed_log']

@subcmd('info')
def cmd_info(handler, amo, args):
    handler.add_argument('addon', help='the addon id or url to show info about')
    args = handler.parse_args(args)

    review = amo.get_review(args.addon)
    print("%s (%s)" % (review.addonname, review.url))
    for version in review.versions:
        print("\tVersion %s @ %s" % (version.version, version.date))
        for fileobj in version.files:
            print("\t\tFile #%s (%s): %s" % (fileobj.addonid, fileobj.status, fileobj.url))
        if version.sources:
            print("\t\tSources: %s" % version.sources)

@subcmd('list')
def cmd_list(handler, amo, args):
    handler.add_argument('-u', '--url', action='store_true',
                         help='output add-on urls only')
    handler.add_argument('queue', nargs='?',
                         choices=ALL_QUEUES.keys(),
                         metavar="{" + ",".join(sorted(QUEUES.keys())) + "}",
                         default=DEFAULT_QUEUE,
                         help='the queue to list')
    args = handler.parse_args(args)

    queue = amo.get_queue(ALL_QUEUES[args.queue])

    if args.url:
        for entry in queue:
            print(entry.url)
    else:
        print(*queue, sep="\n")

# pylint: disable=too-many-branches
@subcmd('get')
def cmd_get(handler, amo, args):
    handler.add_argument('-o', '--outdir', default=os.getcwd(),
                         help='output directory for add-ons')
    handler.add_argument('-l', '--limit', type=int, default=1,
                         help='number of versions to download')
    handler.add_argument('-v', '--version', action='append',
                         help='pull a specific version')
    handler.add_argument('addon',
                         help='the addon id or url to get')
    args = handler.parse_args(args)

    review = amo.get_review(args.addon)
    addonpath = os.path.join(args.outdir, review.addonid)

    if os.path.exists(review.addonid):
        print("Warning: add-on directory already exists and may contain stale files")
    else:
        os.mkdir(review.addonid)

    if args.version:
        argversions = set(args.version)
        versions = [v for v in review.versions if v.version in argversions]
        if len(versions) < 1:
            print("Error: could not find version %s" % args.version)
            return

    else:
        versions = review.versions[-args.limit:]

    for version in versions:
        print('Getting version %s %s' % (review.addonid, version.version))
        for fileobj in version.files:
            print('\tGetting file %s' % fileobj.filename)
            xpioutdir = os.path.join(addonpath, fileobj.filename.replace('.xpi', ''))

            fileobj.save(addonpath)
            fileobj.extract(xpioutdir)

        if version.sources:
            sys.stdout.write('\tGetting sources')

            version.savesources(addonpath)
            print(' ' + os.path.basename(version.sourcepath))

            sourceoutdir = os.path.splitext(version.sourcepath)[0]
            version.extractsources(sourceoutdir)

@subcmd('decide')
def cmd_decide(handler, amo, args):
    handler.add_argument('-m', '--message', help='comment add to the review')
    handler.add_argument('addon', help='the addon id or url to decide about')
    handler.add_argument('action', choices=DEFAULT_MESSAGE.keys(), help='the action to execute')
    args = handler.parse_args(args)

    review = amo.get_review(args.addon)

    if not args.message:
        editor = os.environ.get('EDITOR', 'vim')

        msgdir = tempfile.mkdtemp()
        msgfile = os.path.join(msgdir, "addon review message")
        try:
            name = None
            with open(msgfile, "w") as fd:
                fd.write(DEFAULT_MESSAGE[args.action])
                name = fd.name
            subprocess.call([editor, name])

            with open(msgfile, "r") as fd:
                args.message = fd.read()
        finally:
            shutil.rmtree(msgdir)

    if args.action not in review.actions:
        print("Error: Action not valid for this review (%s)" % (",".join(review.actions)))
        return

    version = review.versions[-1]

    print("Giving %s review to %d files in %s %s" % (
        args.action, len(version.files), review.addonname, version.version
    ))
    time.sleep(3)

    version.decide(args.action, args.message)
    print("Done")

@subcmd('logs')
def cmd_logs(handler, amo, args):
    handler.add_argument('-l', '--limit', type=int, default=sys.maxint,
                         help='maximum number of entries to retrieve')
    handler.add_argument('-s', '--start',
                         help='start time range (in local timezone')
    handler.add_argument('-e', '--end',
                         help='end time range (in local timezone, inclusive)')
    handler.add_argument('-q', '--query',
                         help='filter by add-on, editor or comment')
    handler.add_argument('-k', '--key', choices=LOG_SORTKEYS,
                         help='sort by the given key')
    handler.add_argument('-u', '--url', action='store_true',
                         help='output add-on urls only')
    handler.add_argument('logs', nargs='?', default=REVIEW_LOGS[0], choices=REVIEW_LOGS,
                         help='the type of logs to retrieve')
    args = handler.parse_args(args)

    logs = amo.get_logs(args.logs, start=args.start, end=args.end,
                        query=args.query, limit=args.limit)

    if args.key:
        logs = sorted(logs, key=lambda entry: getattr(entry, args.key))

    if args.url:
        logs = uniq([entry.url for entry in logs])

    print(*logs, sep="\n")


@subcmd('upload')
def cmd_upload(handler, amo, args):
    handler.add_argument('-v', '--verbose', action='store_true',
                         help='show validation messages')
    handler.add_argument('-x', '--xpi', nargs=2, action='append',
                         required=True,
                         metavar=('{all,linux,mac,win,android}', 'XPI'),
                         help='upload an xpi for a platform')
    handler.add_argument('-b', '--beta', action='store_true',
                         help='force uploading this xpi to the beta channel')
    handler.add_argument('-s', '--source',
                         help='add sources to this submission')
    handler.add_argument('addon',
                         help='the addon id to upload')
    args = handler.parse_args(args)

    for platform, xpi in args.xpi:
        print("Uploading %s for platform %s" % (xpi, platform))
        report = amo.upload(args.addon, xpi, platform)
        print(report)
        report.show_messages('all' if args.verbose else 'error')

        if RE_VERSION_BETA.search(report.version) and not args.beta:
            print("Version %s matches the beta pattern, uploading as beta" % report.version)
            args.beta = True

        if report.success:
            print("Adding version %s" % report.version)
            url = amo.add_xpi_to_version(args.addon, report, platform, args.source, beta=args.beta)
            print("New version added at %s" % url)
        else:
            if len(args.xpi) > 1:
                print("Cancelling uploads, validation has failed")
            break

def uniq(seq):
    previous = None
    for value in seq:
        if previous != value:
            yield value
            previous = value

def init_logging(level, _):
    logging.basicConfig()
    logging.getLogger().setLevel(level)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(level)
    requests_log.propagate = True

    if level == logging.DEBUG:
        httplib.HTTPConnection.debuglevel = 1

def login_prompter_impl():
    username = raw_input("Username: ").strip()
    password = getpass.getpass("Password: ").strip()
    return username, password

def main():
    amo = AddonsService(login_prompter=login_prompter_impl)
    cookiedefault = os.path.expanduser('~/.amo_cookie')

    def load_context(args):
        amo.session.load(args.cookies)
        return amo

    handler = ArgumentHandler()
    handler.add_argument('-c', '--cookies', default=cookiedefault,
                         help='the file to save the session cookies to')
    handler.set_logging_argument('-d', '--debug', default_level=logging.WARNING,
                                 config_fxn=init_logging)
    handler.run(sys.argv[1:], context_fxn=load_context)
    amo.persist()

if __name__ == '__main__':
    main()
