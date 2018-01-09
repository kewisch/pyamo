# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

from __future__ import print_function

import sys
import os
import time

from urlparse import urljoin
from datetime import timedelta
from tzlocal import get_localzone
from dateutil import parser as dateparser
from requests.exceptions import HTTPError

from .queue import QueueEntry
from .logs import LogEntry
from .review import Review
from .session import AmoSession
from .validation import ValidationReport
from .utils import AMO_BASE, AMO_EDITOR_BASE, AMO_DEVELOPER_BASE, \
    AMO_TIMEZONE, VALIDATION_WAIT, UPLOAD_PLATFORM, csspath

import lxml.html


class AddonsService(object):
    def __init__(self, login_prompter=None, cookiefile=None):
        self.session = AmoSession(self, login_prompter, cookiefile=cookiefile)

    def persist(self):
        self.session.persist()

    def get_review(self, id_or_url):
        review = Review(self, id_or_url)
        review.get()
        return review

    def _unpaginate(self, url, func, params=None, limit=sys.maxint):
        things = []
        lastlen = -1

        while url and len(things) < limit:
            req = self.session.get(url, stream=True, params=params)
            req.raw.decode_content = True
            doc = lxml.html.parse(req.raw).getroot()
            lastlen = len(things)
            nexturl = func(things, doc)
            thislen = len(things)

            if lastlen == thislen:
                break

            if thislen > limit:
                things = things[:limit]

            # Get the next url and make sure to unset parameters, since they
            # will be provided in the next url anyway.
            url = urljoin(AMO_EDITOR_BASE, nexturl) if nexturl else None
            params = None

        return things

    def get_queue(self, name_or_url):
        if name_or_url.startswith(AMO_BASE) or name_or_url.startswith(AMO_EDITOR_BASE):
            name = "/".join(name_or_url.split("/")[-2])
        else:
            name = name_or_url

        def page(queue, doc):
            queuerows = doc.xpath(csspath('#addon-queue > tbody > .addon-row'))
            for row in queuerows:
                queue.append(QueueEntry(self.session, row))

            nextlink = doc.xpath(csspath('.data-grid-top > .pagination > li > a[rel="next"]'))
            return nextlink[0].attrib['href'] if len(nextlink) else None

        url = '%s/%s' % (AMO_EDITOR_BASE, name)
        return self._unpaginate(url, page)

    def get_logs(self, loglist, start=None, end=None, query=None, limit=sys.maxint):
        # pylint: disable=too-many-arguments
        payload = {
            'search': query
        }

        dtstart = None
        dtend = None
        localtz = get_localzone()

        # We need to offset the date a bit so the returned results are in the
        # user's local timezone. If specific times were passed then don't
        # expand the end date to the end of the day.
        if start:
            dtstart = localtz.localize(dateparser.parse(start))
            payload['start'] = dtstart.astimezone(AMO_TIMEZONE).strftime('%Y-%m-%d')

        if end:
            dtend = localtz.localize(dateparser.parse(end))
            if dtend.hour == 0 and dtend.minute == 0 and dtend.second == 0:
                dtend += timedelta(days=1)
            payload['end'] = dtend.astimezone(AMO_TIMEZONE).strftime('%Y-%m-%d')

        def page(logs, doc):
            logrows = doc.xpath(csspath('#log-listing > tbody > tr[data-addonid]'))
            for row in logrows:
                entry = LogEntry(self.session, row)
                if (not dtstart or entry.date >= dtstart) and \
                   (not dtend or entry.date <= dtend):
                    logs.append(entry)

            nextlink = doc.xpath(csspath('.pagination > li > a[rel="next"]'))
            return nextlink[0].attrib['href'] if len(nextlink) else None

        url = '%s/%s' % (AMO_EDITOR_BASE, loglist)
        return self._unpaginate(url, page, params=payload, limit=limit)

    def upload(self, addonid, xpi, platform='all'):
        if platform not in UPLOAD_PLATFORM:
            raise Exception("Unknown platform %s" % platform)

        uploadurl = None
        url = '%s/addon/%s/versions' % (AMO_DEVELOPER_BASE, addonid)
        req = self.session.get(url, stream=True)
        req.raw.decode_content = True
        doc = lxml.html.parse(req.raw).getroot()
        token = doc.xpath(csspath('form input[name="csrfmiddlewaretoken"]'))[0].attrib['value']

        with open(xpi, 'rb') as xpifd:
            payload = {
                'csrfmiddlewaretoken': (None, token),
                'upload': (os.path.basename(xpi), xpifd, 'application/x-xpinstall')
            }

            uploadurl = '%s/addon/%s/upload-listed' % (AMO_DEVELOPER_BASE, addonid)

            req = self.session.post(uploadurl, files=payload, allow_redirects=False)
            if req.status_code != 302:
                raise Exception('Could not upload %s' % xpi)
            uploadurl = req.headers['location']

        return self.wait_for_validation(addonid, uploadurl, platform)

    def wait_for_validation(self, addonid, uploadurl, platform='all', interval=VALIDATION_WAIT):
        if platform not in UPLOAD_PLATFORM:
            raise Exception("Unknown platform %s" % platform)

        report = None
        while not report or not report.completed:
            req = self.session.get(uploadurl)
            report = ValidationReport(addonid, req.json(), platform)

            if not report.success:
                return report
            elif not report.completed:
                print("Waiting for validation...")
                time.sleep(interval)

        return report

    def add_xpi_to_version(self, addonid, report, platform, source=None, beta=False):
        # pylint: disable=too-many-locals,too-many-branches,too-many-arguments
        sourcefd = None
        try:
            url = '%s/addon/%s/versions' % (AMO_DEVELOPER_BASE, addonid)
            req = self.session.get(url, stream=True)
            req.raw.decode_content = True
            doc = lxml.html.parse(req.raw).getroot()
            token = doc.xpath(csspath('form input[name="csrfmiddlewaretoken"]'))[0].attrib['value']

            ver_exists = doc.xpath(csspath(".item_wrapper a") +
                                   "[contains(text(), 'Version %s')]" % report.version)
            if len(ver_exists):
                final_version_url = urljoin(AMO_DEVELOPER_BASE, ver_exists[0].attrib['href'])
                add_version_url = final_version_url + "/submit-file/"
            else:
                final_version_url = None  # will fill this in later
                add_version_url = '%s/addon/%s/versions/submit/' % (AMO_DEVELOPER_BASE, addonid)

            payload = {
                'csrfmiddlewaretoken': (None, token),
                'upload': (None, report.reportid),
                'supported_platforms': (None, UPLOAD_PLATFORM[platform]),
            }

            if beta:
                payload['beta'] = (None, "on")

            if source:
                sourcefd = open(source, 'rb')
                payload['source'] = (os.path.basename(source), sourcefd, 'application/octet-stream')
            else:
                payload['source'] = ("", "", 'application/octet-stream')

            req = self.session.post(add_version_url, files=payload,
                                    allow_redirects=False, timeout=(60.0, 60.0))

            if not final_version_url:
                locparts = req.headers['location'].split("/")
                final_version_url = urljoin(AMO_DEVELOPER_BASE,
                                            "addon/%s/versions/%s" % (addonid, locparts[-2]))

            return final_version_url
        except HTTPError, e:
            if e.response.status_code != 400:
                raise e
            msg = None
            try:
                msg = "Error: %s" % " ".join(e.response.json()['__all__'])
            except (ValueError, KeyError):
                msg = ("Error: %s" % e.response.text)
            raise Exception(msg)
        finally:
            if sourcefd:
                sourcefd.close()
