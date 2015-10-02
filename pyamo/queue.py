# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from .utils import AMO_EDITOR_BASE

from urlparse import urljoin

class QueueEntry(object):
    # pylint: disable=too-few-public-methods

    def __init__(self, session, row):
        self.addonnum = row.attrib['data-addon'].replace('addon-', '')

        _, hrefrow, typerow, agerow, _, _, _, _, _ = row.getchildren()

        anchor = hrefrow.getchildren()[0]

        self.url = urljoin(AMO_EDITOR_BASE, anchor.attrib['href'])
        self.name = anchor.text.strip()
        self.version = anchor.getchildren()[0].text.strip()
        self.addontype = typerow.text
        self.age = agerow.text
        self.session = session

    def __str__(self):
        return '%s - %s %s' % (self.age.ljust(10), self.name, self.version)
