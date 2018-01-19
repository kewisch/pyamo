# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2017

from __future__ import print_function

import sys

from .utils import AMO_BASE, AMO_ADMIN_BASE, AMO_EDITOR_BASE, REV_ADDON_STATE, \
                   REV_ADDON_FILE_STATE, csspath
import lxml.html


class AdminInfo(object):

    def __init__(self, parent, id_or_url):
        if id_or_url.startswith(AMO_BASE) or id_or_url.startswith(AMO_EDITOR_BASE):
            addonid = id_or_url.split("/")[-1]
        else:
            # Strip slashes, sometimes added due to bash directory completion
            addonid = id_or_url.rstrip('/')

        self.parent = parent
        self.session = parent.session
        self.addonid = addonid
        self.versions = []
        self.addonstatus = -1
        self.page = 0
        self.status = None

        self.url = '%s/addon/manage/%s/' % (AMO_ADMIN_BASE, addonid)

    def get(self):
        self.versions = []
        self.page = 0
        self.get_admin_page(1)

    def get_next_page(self):
        return self.get_admin_page(self.page + 1)

    def get_all_versions(self):
        self.versions = []
        incomplete = True
        while incomplete:
            incomplete = self.get_next_page()

    def get_admin_page(self, page=1):
        req = self.session.get(self.url + "?page=%d" % page, stream=True, allow_redirects=False)

        if req.status_code == 302:
            if 'messages' not in req.cookies:
                raise Exception("Invalid response")
            message = req.cookies['messages'].split("\\\\n")
            if len(message) != 4:
                raise Exception("Invalid response")

            raise Exception(message[1].strip())

        req.raw.decode_content = True
        doc = lxml.html.parse(req.raw).getroot()

        first_page_path = ".pagination > li.selected > a"
        first_page_node = doc.xpath(csspath(first_page_path))
        is_first_page = first_page_node[0].text == "1" if len(first_page_node) else True

        if page > 1 and is_first_page:
            # We've gone over the last page, need to bail early
            return False

        statusnode = doc.xpath(csspath('form > p > select > option[selected]'))[0]
        tokennode = doc.xpath(csspath('form input[name="csrfmiddlewaretoken"]'))[0]
        self.status = int(statusnode.attrib['value'])
        self.token = tokennode.attrib['value']

        versions = []
        headrow = None
        for row in doc.xpath(csspath('form > table > tbody > tr')):
            if len(row.getchildren()) == 7:
                headrow = row

            versions.append(AdminFile(self, row, headrow))

        self.versions = self.versions + versions
        self.page = page
        return True

    def checkstatus(self):
        def getstat(status=self.status):
            return REV_ADDON_STATE.get(status, status)

        if self.status == 4 and all(version.status == 5 for version in self.versions):
            raise Exception('Status is "%s" but should be "%s" or "%s"' %
                            (getstat(), getstat(0), getstat(5)))

        if self.status == 0 and any(version.status == 4 for version in self.versions):
            raise Exception('Status is "%s" but should be "%s"' % (getstat(), getstat(4)))

        if self.status == 5 and any(version.status != 5 for version in self.versions):
            raise Exception('Status is "%s" but not all versions are disabled' % getstat())

    @property
    def all_versions(self):
        return [version.version for version in self.versions]

    def formdata(self, changedonly=False):
        data = {
          'form-TOTAL_FORMS': len(self.versions),
          'form-INITIAL_FORMS': len(self.versions),
          'form-MIN_NUM_FORMS': 0,
          'form-MAX_NUM_FORMS': 1000,
          'csrfmiddlewaretoken': self.token,
          'status': self.status
        }
        formid = 0
        for version in self.versions:
            if changedonly and not version.changed:
                continue

            data['form-%s-id' % formid] = version.fileid
            data['form-%s-status' % formid] = version.status
            formid += 1
        return data

    def save(self, changedonly=False):
        req = self.session.post(self.url, data=self.formdata(changedonly), allow_redirects=False)
        if req.status_code != 200:
            req.raise_for_status()

    def versions_to_status(self, versions, status):
        versionset = set(versions)
        for version in self.versions:
            if version.version in versionset:
                version.status = status
                versionset.remove(version.version)

        if len(versionset):
            raise Exception('Unknown versions: ' + ", ".join(versionset))


class AdminFile(object):

    def __init__(self, parent, row, headrow):
        self.parent = parent

        if row == headrow:
            datecell, versioncell, channelcell, filecell, platformcell, \
                statuscell, hashcell = row.getchildren()
        else:
            datecell, versioncell, channelcell, _, _, _, _ = headrow.getchildren()
            _, filecell, platformcell, statuscell, hashcell = row.getchildren()

        self.date = datecell.text.encode('utf-8')
        self.version = versioncell.getchildren()[0].text
        self.channel = channelcell.text
        self.fileid = int(filecell.getchildren()[0].text)
        self.platform = platformcell.text
        self.status = int(statuscell.xpath(csspath('option[selected]'))[0].attrib['value'])
        self.originalstatus = self.status

        self.formid = statuscell.getchildren()[1].attrib['name'].split('-')[1]
        self.hash = hashcell.getchildren()[0].attrib['title']

    @property
    def changed(self):
        return self.originalstatus != self.status

    def __unicode__(self):
        return u'%s (%s, id %s, %s) for %s: %s [%s]' % (
            self.version.ljust(20), self.channel, self.fileid,
            self.date.rjust(14), self.platform.ljust(13),
            REV_ADDON_FILE_STATE.get(self.status, self.status).ljust(8),
            self.hash
        )

    def __str__(self):
        return unicode(self).encode(sys.stdout.encoding or 'ascii', 'replace')
