# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import sys

from urlparse import urljoin

from .utils import AMO_EDITOR_BASE


class QueueEntry(object):
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, session, row):
        self.addonnum = row.attrib['data-addon'].replace('addon-', '')

        _, hrefrow, typerow, agerow, _, _, _, _, _ = row.getchildren()

        anchor = hrefrow.getchildren()[0]
        self.addonid = anchor.attrib['href'].split("/")[-1]

        self.url = urljoin(AMO_EDITOR_BASE, anchor.attrib['href'])
        self.name = anchor.text.strip()
        self.version = anchor.getchildren()[0].text.strip()
        self.addontype = typerow.text
        self.age = agerow.text
        self.session = session

    def __unicode__(self):
        return u'%s - %s %s [%s]' % (self.age.ljust(10), self.name, self.version, self.addonid)

    def __str__(self):
        return unicode(self).encode(sys.stdout.encoding, 'replace')
