# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import sys
import six
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error

from six.moves.urllib.parse import urljoin
from dateutil import parser as dateparser
from tzlocal import get_localzone

from .utils import AMO_EDITOR_BASE, AMO_TIMEZONE


class LogEntry(object):
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, session, row):
        self.addonnum = row.attrib['data-addonid']

        dtcell, msgcell, editorcell, _ = row.getchildren()
        nameelem, actionelem = msgcell.getchildren()

        self.date = AMO_TIMEZONE.localize(dateparser.parse(dtcell.text))
        self.addonname = nameelem.text.strip()
        self.addonid = six.moves.urllib.parse.unquote(actionelem.attrib['href'].split('/')[-1]).decode('utf8')
        self.url = urljoin(AMO_EDITOR_BASE, actionelem.attrib['href'])
        self.version = nameelem.tail.strip()
        self.reviewer = editorcell.text.strip()
        self.action = actionelem.text.strip()
        self.session = session

    def __unicode__(self):
        localdt = self.date.astimezone(get_localzone()).strftime('%Y-%m-%d %I:%M:%S')
        return u'%s %s %s %s %s %s' % (
            localdt, self.reviewer.ljust(20), self.action.ljust(25),
            self.addonid.ljust(30), self.addonname, self.version
        )

    def __str__(self):
        return unicode(self).encode(sys.stdout.encoding or "utf-8", 'replace')
