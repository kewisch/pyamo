# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import sys
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

    def _unpaginate(self, url, func, params=None, limit=sys.maxint):
        things = []

        while url and len(things) < limit:
            req = self.session.get(url, stream=True, params=params)
            doc = lxml.html.parse(req.raw).getroot()
            nexturl = func(things, doc)

            # Get the next url and make sure to unset parameters, since they
            # will be provided in the next url anyway.
            url = urljoin(AMO_EDITOR_BASE, nexturl) if nexturl else None
            params = None

        return things

    def get_queue(self, name_or_url):
        if name_or_url.startswith(AMO_BASE):
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

                if len(logs) >= limit:
                    break

            nextlink = doc.xpath(csspath('.pagination > li > a[rel="next"]'))
            return nextlink[0].attrib['href'] if len(nextlink) else None

        url = '%s/%s' % (AMO_EDITOR_BASE, loglist)
        return self._unpaginate(url, page, params=payload, limit=limit)
