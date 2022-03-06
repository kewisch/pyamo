# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2021

import lxml.html
from .utils import AMO_BASE, AMO_USER_BASE, csspath


class User:
    _cache = {}

    @staticmethod
    def getcache(parent, id_or_url, expand=False):
        user = User(parent, id_or_url)
        if user.userid not in User._cache:
            User._cache[user.userid] = user

        if expand:
            user.get()

        return User._cache[user.userid]

    def __init__(self, parent, id_or_url):
        id_or_url = str(id_or_url)
        if id_or_url.startswith(AMO_BASE) or id_or_url.startswith(AMO_USER_BASE):
            userid = id_or_url.split("/")[-1]
        else:
            # Strip slashes, sometimes added due to bash directory completion
            userid = id_or_url.rstrip('/')

        self.parent = parent
        self.session = parent.session
        self.userid = userid
        self.email = None

        self.url = '%s/%s/edit' % (AMO_USER_BASE, userid)

    def get(self):
        if self.email:
            return self

        req = self.session.get(self.url, stream=True)

        req.raw.decode_content = True
        doc = lxml.html.parse(req.raw).getroot()
        self.email = doc.xpath(csspath(".UserProfileEdit-email"))[0].attrib['value']

        return self
