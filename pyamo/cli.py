#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import os
import shutil
import sys
import time
import json

import getpass
import logging
import subprocess
import tempfile
import http.client

from arghandler import subcmd, ArgumentHandler
from .service import AddonsService
from .utils import find_binary, runprofile, handler_defaults, ValidateFlags, \
                   requiresvpn, RE_VERSION, RE_VERSION_BETA, ADDON_STATE, ADDON_FILE_STATE, \
                   REV_ADDON_STATE, REV_ADDON_FILE_STATE

DEFAULT_MESSAGE = {
    'confirm_auto_approved': '',
    'public': 'Your add-on submission has been approved.',
    'reject': 'Your version was rejected because of the following problems:',
    'reject_multiple_versions': 'Your versions were rejected because of the following problems:',
    'reply': 'Please provide us with detailed information on how to test your add-on.',
    'super': 'halp!',
    'comment': 'FYI: bananas!'
}

QUEUES = {
    'unlisted/nominated': 'unlisted_queue/nominated',
    'unlisted/pending': 'unlisted_queue/pending',
    'new': 'queue/new',
    'updates': 'queue/updates'
}
ALL_QUEUES = QUEUES.copy()
ALL_QUEUES.update({v: v for v in list(QUEUES.values())})
DEFAULT_QUEUE = 'new'

LOG_SORTKEYS = [
    'date', 'addonname', 'version', 'reviewer', 'action'
]

REVIEW_LOGS = ['reviewlog']


@subcmd('flags', help="Shows and sets flags for an add-on")
def cmd_debugtest(handler, amo, args):
    handler.add_argument('-s' '--set', dest='flags', nargs=2,
                         action=ValidateFlags, metavar=('FLAG', 'VALUE'),
                         help='flag(s) to set')
    handler.add_argument('addon', nargs='*', help='the addon to get or set flags for')
    args = handler.parse_args(args)

    def mapvalue(val):
        if val is None:
            return "null"
        elif val is True:
            return "true"
        elif val is False:
            return "false"
        else:
            return val

    for addon in args.addon:
        review = amo.get_review(addon)
        flags = review.flags(args.flags or {})
        print("{} ({}, {} users)".format(addon, review.addonname, review.adu))
        if len(flags.keys()) > 0:
            print("\t" + "\n\t".join("{} = {}".format(key, mapvalue(value))
                                     for key, value in flags.items()))


@subcmd('unsubscribe', help="Unsubscribe to updates for an add-on")
def cmd_unsubscribe(handler, amo, args):
    handlesubscription(handler, amo, args, False)


@subcmd('subscribe', help="Subscribe to updates for an add-on")
def cmd_subscribe(handler, amo, args):
    handlesubscription(handler, amo, args, True)


def handlesubscription(handler, amo, args, subscribe):
    subscribestring = "" if subscribe else "un"
    handler.add_argument('-u', '--unlisted', action='store_true',
                         help='{}subscribe to unlisted updates'.format(subscribestring))
    handler.add_argument('addon', nargs='*',
                         help='the addon to {}subscribe to'.format(subscribestring))
    args = handler.parse_args(args)

    for addon in args.addon:
        review = amo.get_review(addon, unlisted=args.unlisted)
        if review.subscription(subscribe):
            print(
                "{} {} for {} updates".format(
                    "subscribed to" if subscribe else "unsubscribed from",
                    addon,
                    "unlisted" if args.unlisted else "listed"
                )
            )
        else:
            print(
                "error {} {} for {} updates".format(
                    "subscribing to" if subscribe else "unsubscribing from",
                    addon,
                    "unlisted" if args.unlisted else "listed"
                )
            )


@subcmd('adminget', help="Show admin manage information about an add-on")
@requiresvpn
def cmd_admin(handler, amo, args):
    handler.add_argument('addon', help='the addon id or url to show info about')
    handler.add_argument('-b', '--beta', action='store_true', help='include beta releases')
    handler.add_argument('-f', '--file', action='store_true',
                         help='output in a format saving status to file')
    args = handler.parse_args(args)

    admininfo = amo.get_admin_info(args.addon)

    if not args.file:
        print('Addon %s has state "%s"' % (args.addon, REV_ADDON_STATE[admininfo.status]))

    filedata = {}
    for ver in reversed(admininfo.versions):
        if not args.beta and ver.status == ADDON_FILE_STATE['beta']:
            continue

        if args.file:
            filedata[ver.fileid] = ver.status
        else:
            print(ver)

    if args.file:
        print(json.dumps({"status": admininfo.status, "files": filedata}, indent=2))


@subcmd('admindisable',
        help="Admin disable one or more add-ons, optionally with a rejection message")
def cmd_admindisable(handler, amo, args):
    handler.add_argument('addon', nargs='*', help='the addon id to disable')
    handler.add_argument('-u', '--user', help='Disable all found add-ons by this user')
    handler.add_argument('-c', '--channel', default=None,
                         help='Disable only add-ons with this channel')
    handler.add_argument('-s', '--status', default=None,
                         help='Disable only add-ons with this status')
    handler.add_argument('-U', '--unlisted', action='store_true',
                         help='assume ids are unlisted')
    handler.add_argument('-m', '--message', default=None, help='Also send a rejection message')
    args = handler.parse_args(args)

    if args.addon and args.user:
        print("Error: can't specify both addons and user argument")
        return

    addons = None
    if args.user:
        addoninfo = amo.get_user_addons(args.user)
        addoninfo.filter(status=args.status, channel=args.channel)

        print("Will disable the following add-ons:\n")
        print(addoninfo)
        print("\nReady to go? (Ctrl+C to cancel)")
        input()

        addons = addoninfo.get_ids()
    else:
        print("Will disable %d add-ons, ready to go? (Ctrl+C to cancel)" % len(args.addon))
        input()
        addons = args.addon

    sys.stdout.write("Disabling...")
    sys.stdout.flush()
    for addon in addons:
        review = amo.get_review(addon, unlisted=args.unlisted)
        success = True
        if args.message:
            versionids = review.get_enabled_version_numbers()
            success = review.decide("reject_multiple_versions", args.message, versionids=versionids)

        if success and review.admin_disable():
            sys.stdout.write(".")
        else:
            sys.stdout.write("E(%s)" % addon)
        sys.stdout.flush()

    print("Done!")


@subcmd('adminchange',
        help="Change the status of an add-ons and its files using the admin manage page")
@requiresvpn
def cmd_adminstatus(handler, amo, args):  # pylint: disable=too-many-branches,too-many-statements
    handler.add_argument('addon', help='the addon id or url to show info about')
    handler.add_argument('-s', '--status', default=None, help='set the add-on status')
    handler.add_argument('-a', '--approve', nargs='+', help='set these versions to approved')
    handler.add_argument('-d', '--disable', nargs='+', help='set these versions to disabled')
    handler.add_argument('-X', '--disable-all', action='store_true', help='disable all versions')
    handler.add_argument('-O', '--approve-all', action='store_true', help='approve all versions')
    handler.add_argument('-f', '--file', help='load states from file')
    args = handler.parse_args(args)

    admininfo = amo.get_admin_info(args.addon)
    oldstatus = admininfo.status

    if args.file:
        # Read from file mode
        if args.status or args.approve or args.disable or args.disable_all or args.approve_all:
            print("State change options not valid with -f")
            return

        with open(args.file) as fd:
            jsondata = json.loads(fd.read())

        statuschanged = (jsondata['status'] != admininfo.status)

        if statuschanged:
            print("Changing state %s -> %s" % (
                ADDON_STATE[admininfo.status], ADDON_STATE[jsondata['status']]
            ))
        admininfo.status = jsondata['status']

        files = jsondata['files']

        for version in admininfo.versions:
            key = str(version.fileid)
            if key in files:
                version.status = files[key]
                if version.changed:
                    print("Version %s File %s (%s) changing from %s to %s" % (
                        version.version, version.fileid, version.platform,
                        REV_ADDON_FILE_STATE.get(version.originalstatus, version.originalstatus),
                        REV_ADDON_FILE_STATE.get(version.status, version.status)
                    ))

    else:
        # Normal mode, use command line arguments to set status
        args.approve = fixlist(args.approve)
        args.disable = fixlist(args.disable)

        approveset = set()
        disableset = set()

        if args.approve_all:
            approveset.update(admininfo.all_versions)
            if not args.disable:
                admininfo.status = ADDON_STATE['approved']

        if args.disable_all:
            disableset.update(admininfo.all_versions)
            if not args.approve:
                admininfo.status = ADDON_STATE['disabled']

        if args.approve:
            approveset |= set(args.approve)
            disableset -= set(args.approve)
        if args.disable:
            disableset |= set(args.disable)
            approveset -= set(args.disable)

        admininfo.versions_to_status(approveset, ADDON_FILE_STATE['approved'])
        admininfo.versions_to_status(disableset, ADDON_FILE_STATE['disabled'])

        if args.status is not None:
            try:
                admininfo.status = int(args.status)
            except ValueError:
                # Not an int, but a string
                if args.status not in ADDON_STATE:
                    print("Invalid add-on state %s" % args.status)
                    return
                else:
                    admininfo.status = ADDON_STATE[args.status]

        statuschanged = (oldstatus != admininfo.status)
        if statuschanged:
            print("Changing state for %s: %s -> %s" %
                  (args.addon, REV_ADDON_STATE[oldstatus], REV_ADDON_STATE[admininfo.status]))
        else:
            print("Keeping state for %s: %s" % (args.addon, REV_ADDON_STATE[admininfo.status]))

        if len(disableset) > 0:
            print("Marking these versions disabled: " + ", ".join(disableset))
        if len(approveset) > 0:
            print("Marking these versions approved: " + ", ".join(approveset))

    # Sanity Check
    admininfo.checkstatus()

    if not any(version.changed for version in admininfo.versions) and not statuschanged:
        print("Nothing changed, not sending request")
        return

    if args.file:
        print("Last chance to bail out before changes are made (Ctrl+C to quit, enter to continue)")
        input()

    admininfo.save()
    print("Done")


@subcmd('info', help="Show basic information about an add-on")
def cmd_info(handler, amo, args):
    handler.add_argument('addon', nargs='*', help='the addon id or url to show info about')
    handler.add_argument('-f', '--files', action='store_true',
                         help='Show information about versions and files')
    handler.add_argument('-s', '--stats', action='store_true',
                         help='Show usage statistics')
    args = handler.parse_args(args)

    adu_total = 0
    adu_max = 0
    downloads_total = 0

    for addon in args.addon:
        review = amo.get_review(addon)
        print("%s (%s)" % (review.addonname, review.url))
        if args.stats:
            print("\tDownloads: %d\n\tActive Daily Users: %d" % (review.downloads, review.adu))
            adu_total += review.adu
            downloads_total += review.downloads
            adu_max = max(adu_max, review.adu)
        if args.files:
            for version in review.versions:
                print("\tVersion %s @ %s" % (version.version, version.date))
                for fileobj in version.files:
                    print("\t\tFile #%s (%s): %s" % (fileobj.fileid, fileobj.status, fileobj.url))
                if version.sources:
                    print("\t\tSources: %s" % version.sources)

    if args.stats and len(args.addon) > 1:
        print("\nTotal downloads: %d\nTotal Active Daily Users: %d" % (downloads_total, adu_total))
        print("Maximum Active Daily Users: %d" % (adu_max))


@subcmd('list', help="List add-ons in the given queue")
def cmd_list(handler, amo, args):
    handler.add_argument('-u', '--url', action='store_true',
                         help='output add-on urls only')
    handler.add_argument('-n', '--numericid', action='store_true',
                         help='output numeric add-on ids only')
    handler.add_argument('-i', '--ids', action='store_true',
                         help='output add-on ids only')
    handler.add_argument('queue', nargs='?',
                         choices=list(ALL_QUEUES.keys()),
                         metavar="{" + ",".join(sorted(QUEUES.keys())) + "}",
                         default=DEFAULT_QUEUE,
                         help='the queue to list')
    args = handler_defaults(handler, 'list').parse_args(args)

    if args.url and args.ids:
        print("Error: can't specify both ids and urls for display")
        return

    queue = amo.get_queue(ALL_QUEUES[args.queue])

    if args.ids:
        for entry in queue:
            print(entry.addonid)
    elif args.url:
        for entry in queue:
            print(entry.url)
    elif args.numericid:
        for entry in queue:
            print(entry.addonnum)
    else:
        print(*queue, sep="\n")


# pylint: disable=too-many-branches,too-many-statements
@subcmd('get', help="Download one or more versions of an add-on, including sources")
def cmd_get(handler, amo, args):
    handler.add_argument('-o', '--outdir', default=os.getcwd(),
                         help='output directory for add-ons')
    handler.add_argument('-d', '--diff', action='store_true',
                         help='shortcut for -v previous -v latest')
    handler.add_argument('-p', '--profile', action='store_true',
                         help='create a profile for each add-on version')
    handler.add_argument('-r', '--run', action='store_true',
                         help='run the application in addition to creating a profile')
    handler.add_argument('--binary',
                         help='path to the binary to run, e.g. Firefox')
    handler.add_argument('-u', '--unlisted', action='store_true',
                         help='use the unlisted review page')
    handler.add_argument('-U', '--user',
                         help='Download all add-ons from a user')
    handler.add_argument('--symlinks', action="store_true",
                         help='Create symlinks for convenience. Works best as a default.')
    handler.add_argument('addon', nargs='+',
                         help='the addon id or url to get')

    versiongroup = handler.add_mutually_exclusive_group()
    versiongroup.add_argument('-l', '--limit', type=int, default=1,
                              help='number of versions to download')
    versiongroup.add_argument('-v', '--version', action='append', default=[],
                              help='pull a specific version. ' +
                                   'Prefix with @ to reference a version id.')
    versiongroup.add_argument('-a', '--all-versions', action='store_true', dest="allversions",
                              help='pull all versions')

    args = handler_defaults(handler, 'get').parse_args(args)

    args.outdir = os.path.expanduser(args.outdir)

    if args.run:
        args.profile = True

    if args.user:
        pass

    for addon in args.addon:
        cmd_get_single(amo, args, addon)


def cmd_get_single(amo, args, addon):
    if addon == '.':
        addon = os.path.basename(os.getcwd())
        if RE_VERSION.search(addon):
            addon = os.path.basename(os.path.dirname(os.getcwd()))

    if len(args.addon) > 1:
        print("Getting add-on %s" % addon)

    review = amo.get_review(addon, args.unlisted)
    if len(review.versions) == 0:
        print("Warning: No listed versions, trying unlisted")
        args.unlisted = True
        review = amo.get_review(addon, args.unlisted)

    addonpath = os.path.join(args.outdir, review.slug)
    cmdpath = os.path.join(args.outdir, addon)

    if os.path.exists(addonpath):
        print("Warning: add-on directory already exists and may contain stale files")
    else:
        os.mkdir(addonpath)

    # If you do `amo get {guid}` it will save the slug. If you have an alias that tries to cd into
    # the passed directory, that fails. This symlink allows for both.
    if args.symlinks and not os.path.exists(cmdpath) and review.slug != addon:
        os.symlink(addonpath, cmdpath)

    if os.path.abspath(args.outdir) != os.getcwd() or review.slug != addon:
        print("Saving add-on to %s" % addonpath)

    if args.diff:
        args.version.extend(('previous', 'latest'))

    if args.allversions:
        versions = review.get_all_versions()
        if len(versions) >= 0:
            print("Retrieving %d versions" % len(versions))
    elif args.version and len(args.version) > 0:
        argversions = set()
        argversionids = set()
        for version in args.version:
            if version.startswith("@"):
                argversionids.add(version[1:])
            else:
                argversions.add(version)

        replace_version_tag(argversions, "latest", review.find_latest_version)
        replace_version_tag(argversions, "latestwx", review.find_latest_version_wx)

        def find_versions(versions, page):
            replace_version_tag(argversions,
                                "previous",
                                review.find_previous_version, quiet=True)
            argmatch = [v for v in versions if v.version in argversions]
            argidmatch = [v for v in versions if v.id in argversionids]

            if len(argmatch) + len(argidmatch) == len(argversions) + len(argversionids):
                return argmatch + argidmatch
            else:
                print("Warning: could not find all requested version on page",
                      "%d, trying next page" % page)
                return False

        versions = review.get_versions_until(find_versions, [])
    else:
        review.get_versions_until(lambda versions, _: len(versions) >= args.limit)
        versions = review.versions[-args.limit:]

    if len(versions) == 0:
        print("Error: no requested versions found")
        return

    for version in versions:
        platforms = ", ".join(version.apps)
        print('Getting version %s %s [%s]' % (review.slug, version.version, platforms))
        for fileobj in version.files:
            fileplatforms = ", ".join(fileobj.platforms)
            print('\tGetting file %s [%s]' % (fileobj.filename, fileplatforms))
            fileobj.save(addonpath)
            fileobj.extract(addonpath)
            if args.profile:
                print('\tCreating profile [%s]' % fileplatforms)
                fileobj.createprofile(addonpath)

        if version.sources:
            sys.stdout.write('\tGetting sources')

            version.savesources(addonpath)
            print(' ' + version.sourcefilename)
            version.extractsources(addonpath)

        if args.symlinks:
            version.linklatest(addonpath)

    if args.run:
        print('Running applicaton for %s %s' % (review.slug, versions[-1].version))
        if not args.binary:
            print("Warning: you should be running unreviewed extensions in a VM for safety")
            args.binary = find_binary("firefox")

        runprofile(args.binary, versions[-1].files[-1])


@subcmd('run', help="Run an add-on in Firefox (preferably in a VM)")
def cmd_run(handler, amo, args):
    handler.add_argument('-o', '--outdir', default=os.getcwd(),
                         help='output directory for add-ons')
    handler.add_argument('-c', '--clear', action='store_true',
                         help='clear the profile if it exists')
    handler.add_argument('--binary',
                         help='path to the binary to run, e.g. Firefox')
    handler.add_argument('addon', help='the addon id to run')
    handler.add_argument('version', help='the addon version to run')
    args = handler_defaults(handler, 'run').parse_args(args)

    args.outdir = os.path.expanduser(args.outdir)
    if os.path.abspath(os.path.expanduser(args.outdir)) != os.getcwd():
        print("Warning: the specified output directory is not the current directory")

    review = amo.get_review(args.addon)

    argversions = [args.version]

    replace_version_tag(argversions, "latest", review.find_latest_version)
    replace_version_tag(argversions, "previous", review.find_previous_version)

    version = next((v for v in review.versions if v.version in argversions))

    addonpath = os.path.join(args.outdir, review.slug)

    version.savedpath = os.path.join(addonpath, version.version, "addon.xpi")
    fileobj = version.files[0]
    fileobj.createprofile(addonpath, delete=args.clear)

    if not args.binary:
        print("Warning: you should be running unreviewed extensions in a VM for safety")
        args.binary = find_binary("firefox")
    runprofile(args.binary, fileobj)


@subcmd('decide', help="Make a review decision for an add-on, along with message")
def cmd_decide(handler, amo, args):
    handler.add_argument('-m', '--message',
                         help='comment add to the review')
    handler.add_argument('-A', '--all', action='store_true',
                         help='apply to all versions, e.g. rejections')
    handler.add_argument('-a', '--action', required=True, choices=list(DEFAULT_MESSAGE.keys()),
                         help='the action to execute')
    handler.add_argument('--versionids',
                         help='comma separaed list of versions, e.g. for reject_multiple_versions')
    handler.add_argument('-U', '--unlisted', action='store_true',
                         help='assume ids are unlisted')
    handler.add_argument('-f', '--force', action='store_true',
                         help='Do not wait 3 seconds before executing the action')
    handler.add_argument('--undelay', action='store_true',
                         help='Remove auto-approval extra delay')
    handler.add_argument('addon', nargs='*',
                         help='the addon id(s) or url(s) to decide about')
    args = handler_defaults(handler, 'decide').parse_args(args)

    if args.message and args.message[0] == "@":
        with open(args.message[1:], "r") as fd:
            args.message = fd.read()
    elif args.message:
        args.message = bytes(args.message, "utf-8").decode('unicode_escape')
    else:
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

    if len(args.addon) == 0:
        print("Error: Nothing to give %s review" % args.action)
        return

    if len(args.addon) == 1 and args.addon[0] == '-':
        try:
            args.addon = sys.stdin.readlines()
        except KeyboardInterrupt:
            return

    if not args.force:
        if len(args.addon) > 1:
            print("Will give %s review to %d add-ons with in 3 seconds" %
                  (args.action, len(args.addon)))
        else:
            print("Will give %s review to %s in 3 seconds" % (args.action, args.addon[0]))
        time.sleep(3)

    failures = []

    for addon in args.addon:
        review = amo.get_review(addon.strip(), unlisted=args.unlisted)
        if args.action not in review.actions:
            actions = ",".join(review.actions)
            print("Error: Action not valid for reviewing %s (%s)" % (review.addonname, actions))
            continue

        if args.all:
            success = review.decide(args.action, args.message, review.versions)
        elif args.versionids:
            versionids = args.versionids.split(",")
            success = review.decide(args.action, args.message, versionids=versionids)
        else:
            success = review.decide(args.action, args.message, [review.versions[-1]])

        if not success:
            failures.append(addon)
        elif args.undelay:
            success = review.remove_extra_delay()
            if not success:
                failures.append(addon)

        print("%s completed" % addon)

    if len(failures) > 0:
        print("The following add-ons failed:\n\t" + "\n\t".join(failures))
    else:
        print("Done")


@subcmd('logs', help="Show the review logs")
def cmd_logs(handler, amo, args):
    handler.add_argument('-l', '--limit', type=int, default=sys.maxsize,
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
    handler.add_argument('-i', '--ids', action='store_true',
                         help='output add-on ids only')
    handler.add_argument('logs', nargs='?', default=REVIEW_LOGS[0], choices=REVIEW_LOGS,
                         help='the type of logs to retrieve')
    args = handler_defaults(handler, 'logs').parse_args(args)

    if args.url and args.ids:
        print("Error: can't specify both ids and urls for display")
        return

    logs = amo.get_logs(args.logs, start=args.start, end=args.end,
                        query=args.query, limit=args.limit)

    if args.key:
        logs = sorted(logs, key=lambda entry: getattr(entry, args.key))

    if args.ids:
        logs = uniq([entry.addonid for entry in logs])
    elif args.url:
        logs = uniq([entry.url for entry in logs])

    print(*logs, sep="\n")


@subcmd('upload', help="Upload an add-on to addons.mozilla.org")
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
    args = handler_defaults(handler, 'upload').parse_args(args)

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


def replace_version_tag(argversions, tag, replaceversionlazy, quiet=False):
    if tag in argversions:
        replaceversion = replaceversionlazy()
        if replaceversion:
            argversions.remove(tag)
            argversions.add(replaceversion.version)
        elif not quiet:
            print("Warning: could not find %s version" % tag)


def uniq(seq):
    previous = None
    for value in seq:
        if previous != value:
            yield value
            previous = value


def fixlist(arg):
    if arg and len(arg) == 1 and "," in arg[0]:
        return arg[0].split(",")
    else:
        return arg


def init_logging(level, _):
    logging.basicConfig()
    logging.getLogger().setLevel(level)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(level)
    requests_log.propagate = True

    if level == logging.DEBUG:
        http.client.HTTPConnection.debuglevel = 1


def login_prompter_impl(mode="login"):
    if mode == "2fa":
        return input("2FA Code: ").strip()
    elif mode == "unblock":
        return input("Unblock Code: ").strip()
    elif mode == "login":
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ").strip()
        return username, password
    else:
        raise Exception("Invalid prompter mode " + mode)


def main():
    amo = AddonsService(login_prompter=login_prompter_impl)
    cookiedefault = os.path.expanduser('~/.amo_cookie')

    def load_context(args):
        if args.profile:
            amo.session.load_firefox_cookies(args.profile)
        else:
            amo.session.load(args.cookies)

        amo.session.timeout = args.timeout
        return amo

    handler = ArgumentHandler(use_subcommand_help=True)
    cookiegroup = handler.add_mutually_exclusive_group()
    cookiegroup.add_argument('-P', '--profile', default=None,
                             help='The Firefox profile to use cookies from')
    cookiegroup.add_argument('-c', '--cookies', default=cookiedefault,
                             help='the file to save the session cookies to')

    handler.add_argument('--timeout', type=int, default=None,
                         help='timeout for http requests')
    handler.set_logging_argument('-d', '--debug', default_level=logging.WARNING,
                                 config_fxn=init_logging)

    handler = handler_defaults(handler, "global")

    try:
        handler.run(sys.argv[1:], context_fxn=load_context)
        amo.persist()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
