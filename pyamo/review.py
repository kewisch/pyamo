# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import cgi
import lxml.html
import magic
import os
import shutil

from zipfile import ZipFile
from urlparse import urlparse, urljoin

from .utils import AMO_BASE, AMO_EDITOR_BASE, csspath
from .lzma import SevenZFile

class Review(object):
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    REVIEW_STATUS_TO_LAST_ACCEPT = {
        "Pending Preliminary Review": ("Preliminarily Reviewed",),
        "Pending Full Review": ("Fully Reviewed",),
        "Rejected": ("Fully Reviewed", "Preliminarily Reviewed")
    }

    def __init__(self, parent, id_or_url):
        if id_or_url.startswith(AMO_BASE):
            addonid = id_or_url.split("/")[-1]
        else:
            addonid = id_or_url

        self.parent = parent
        self.session = parent.session
        self.addonid = addonid
        self.addonname = None
        self.token = None
        self.actions = []
        self.versions = []
        self.url = '%s/review/%s' % (AMO_EDITOR_BASE, addonid)

    def find_latest_version(self):
        if len(self.versions):
            return self.versions[-1]
        else:
            return None

    def find_previous_version(self):
        lateststatus = self.versions[-1].files[0].status
        findstatus = Review.REVIEW_STATUS_TO_LAST_ACCEPT.get(lateststatus, None)

        if not findstatus:
            raise Exception("Don't know how to handle review status %s" % lateststatus)

        for version in reversed(self.versions):
            if len(version.files) and version.files[0].status in findstatus:
                return version
        return None

    def get(self):
        req = self.session.get(self.url, stream=True, allow_redirects=False)

        if req.status_code == 302:
            if 'messages' not in req.cookies:
                raise Exception("Invalid response")
            message = req.cookies['messages'].split("\\\\n")
            if len(message) != 4:
                raise Exception("Invalid response")

            raise Exception(message[1].strip())

        doc = lxml.html.parse(req.raw).getroot()

        self.versions = []
        self.addonname = doc.xpath(csspath('#breadcrumbs > li:last-child'))[0].text
        self.token = doc.xpath(csspath('form input[name="csrfmiddlewaretoken"]'))[0].attrib['value']

        self.actions = [
            i.attrib['value'] for i in doc.xpath(csspath('[name="action"]'))
        ]

        heads = doc.xpath(csspath('#review-files > .listing-header'))
        for head in heads:
            self.versions.append(AddonReviewVersion(self, head, head.getnext()))

class AddonReviewVersion(object):
    def __init__(self, parent, head, body):
        self.parent = parent
        self.session = parent.session

        self.sources = None
        self.sourcepath = None
        self.version = None
        self.files = []

        self._init_head(head)
        self._init_body(body)

    def _init_head(self, head):
        args = head.iterchildren().next().text.encode('utf-8').strip().split(" ")
        _, self.version, _, month, day, year = filter(None, args) # pylint: disable=bad-builtin
        self.date = '%s %s %s' % (month, day, year)

    def _init_body(self, body):
        fileinfo = body.xpath(csspath('.file-info'))
        for info in fileinfo:
            self.files.append(AddonVersionFile(self, info))

        sourcelink = body.xpath(csspath('.files > div > a[href]'))
        if len(sourcelink):
            self.sources = urljoin(AMO_BASE, sourcelink[0].attrib['href'])

    def savesources(self, targetpath, chunksize=16384):
        if self.sources:
            req = self.session.get(self.sources, stream=True)

            _, params = cgi.parse_header(req.headers['content-disposition'])
            filename = params['filename']

            self.sourcepath = os.path.join(targetpath, filename)
            with open(self.sourcepath, 'w') as fd:
                for chunk in req.iter_content(chunksize):
                    fd.write(chunk)

    def extractsources(self, targetpath):
        if not self.sourcepath:
            self.savesources(os.path.basename(targetpath))

        if os.path.exists(targetpath):
            shutil.rmtree(targetpath)
        os.mkdir(targetpath)

        mime = magic.from_file(self.sourcepath, mime=True)

        if mime == "application/x-7z-compressed":
            with SevenZFile(self.sourcepath, 'r') as zf:
                zf.extractall(targetpath)
        elif mime == "application/zip":
            with ZipFile(self.sourcepath, 'r') as zf:
                zf.extractall(targetpath)
        else:
            raise Exception("Don't know how to handle %s" % mime)

    def decide(self, action='prelim', comments=''):
        postdata = {
            'csrfmiddlewaretoken': self.parent.token,
            'action': action,
            'comments': comments,
            'canned_response': '',
            'addon_files': [f.addonid for f in self.files],
            'operating_systems': '', # TODO
            'applications': '' # TODO
        }

        url = '%s/review/%s' % (AMO_EDITOR_BASE, self.parent.addonid)
        req = self.session.post(url, data=postdata, allow_redirects=False)
        return req.status_code == 302

class AddonVersionFile(object):
    def __init__(self, parent, fileinfo):
        self.parent = parent
        self.session = parent.session

        infourl = fileinfo.xpath(csspath('.editors-install'))
        self.url = infourl[0].attrib['href']

        statusdiv = fileinfo.xpath(csspath('.light > div'))
        self.status = statusdiv[0].text.strip()

        urlpath = urlparse(self.url).path
        urlpathparts = urlpath.split('/')
        self.filename = urlpathparts[-1]
        self.addonid = urlpathparts[-2]
        self.savedpath = None


    def get(self):
        if self.savedpath:
            return open(self.savedpath, 'r')
        else:
            return self.session.get(self.url, stream=True)

    def extract(self, targetpath):
        if not self.savedpath:
            self.save(os.path.basename(targetpath))

        if os.path.exists(targetpath):
            shutil.rmtree(targetpath)
        os.mkdir(targetpath)

        with ZipFile(self.savedpath, 'r') as zf:
            zf.extractall(targetpath)

    def save(self, targetpath, chunksize=16384):
        self.savedpath = os.path.join(targetpath, self.filename)

        with open(self.savedpath, 'wb') as fd:
            for chunk in self.session.get(self.url, stream=True).iter_content(chunksize):
                fd.write(chunk)
