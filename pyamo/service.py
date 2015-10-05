# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import lxml.html
from urlparse import urljoin

from .queue import QueueEntry
from .logs import LogEntry
from .review import Review
from .session import AmoSession
from .utils import AMO_BASE, AMO_EDITOR_BASE, AMO_TIMEZONE, csspath

from tzlocal import get_localzone
from datetime import timedelta
from dateutil import parser as dateparser

class AddonsService(object):
    def __init__(self, login_prompter=None, cookiefile=None):
        self.session = AmoSession(self, login_prompter, cookiefile=cookiefile)

    def persist(self):
        self.session.persist()

    def get_review(self, id_or_url):
        review = Review(self, id_or_url)
        review.get()
        return review

    def get_queue(self, name_or_url):
        if name_or_url.startswith(AMO_BASE):
            name = "/".join(name_or_url.split("/")[-2])
        else:
            name = name_or_url

        queue = []
        url = '%s/%s' % (AMO_EDITOR_BASE, name)
        while url:
            req = self.session.get(url, stream=True)
            doc = lxml.html.parse(req.raw).getroot()
            queuerows = doc.xpath(csspath('#addon-queue > tbody > .addon-row'))

            for row in queuerows:
                queue.append(QueueEntry(self.session, row))

            nextlink = doc.xpath(csspath('.data-grid-top > .pagination > li > a[rel="next"]'))
            url = urljoin(url, nextlink[0].attrib['href']) if len(nextlink) else None

        return queue

    def get_logs(self, loglist, start=None, end=None, query=None):
        # pylint: disable=too-many-locals
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

        logs = []
        url = '%s/%s' % (AMO_EDITOR_BASE, loglist)
        while url:
            req = self.session.get(url, params=payload, stream=True)
            doc = lxml.html.parse(req.raw).getroot()
            logrows = doc.xpath(csspath('#log-listing > tbody > tr[data-addonid]'))

            for row in logrows:
                entry = LogEntry(self.session, row)
                if (not dtstart or entry.date >= dtstart) and \
                   (not dtend or entry.date <= dtend):
                    logs.append(entry)

            nextlink = doc.xpath(csspath('.pagination > li > a[rel="next"]'))
            url = urljoin(url, nextlink[0].attrib['href']) if len(nextlink) else None

        return logs
