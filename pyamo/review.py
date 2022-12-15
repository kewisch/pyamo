# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import os
import re
import cgi
import shutil
import traceback
import tarfile

from zipfile import ZipFile, BadZipfile
from urllib.parse import urlparse, urljoin, unquote
from mozprofile import FirefoxProfile
from cmp_version import cmp_version

import lxml.html
import magic

from .utils import AMO_BASE, AMO_EDITOR_BASE, AMO_REVIEWERS_API_BASE, csspath
from .user import User
from .lzma import SevenZFile


class Review:
    # pylint: disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, parent, id_or_url, unlisted=False):
        id_or_url = str(id_or_url)
        if id_or_url.startswith(AMO_BASE) or id_or_url.startswith(AMO_EDITOR_BASE):
            addonid = id_or_url.split("/")[-1]
        else:
            # Strip slashes, sometimes added due to bash directory completion
            addonid = id_or_url.rstrip('/')

        self.parent = parent
        self.session = parent.session
        self.addonid = addonid
        self.addonname = None
        self.token = None
        self.actions = []
        self.versions = []
        self.unlisted = unlisted
        if unlisted:
            self.url = '%s/review-unlisted/%s' % (AMO_EDITOR_BASE, addonid)
        else:
            self.url = '%s/review-listed/%s' % (AMO_EDITOR_BASE, addonid)
        self.page = 0

        self.versionmap = {}
        self.adu = 0
        self.downloads = 0
        self.slug = None
        self.api_token = None
        self.enabledversions = []
        self.developers = []

    def find_latest_version(self):
        if len(self.versions) > 0:
            return self.versions[-1]
        else:
            return None

    def find_latest_version_wx(self):
        for version in reversed(self.versions):
            if any(vfile.permissions for vfile in version.files):
                return version
        return None

    def find_previous_version(self):
        for version in reversed(self.versions[:-1]):
            if version.confirmed:
                return version
        return None

    def get(self):
        self.versions = []
        self.page = 0
        self.get_version_page(1)

    def get_next_page(self):
        return self.get_version_page(self.page + 1)

    def check_redirects(self, req):
        if req.status_code == 302:
            if 'messages' not in req.cookies:
                raise Exception("Invalid response")

            message = req.cookies['messages'].split("\\\\n")
            if len(message) != 4:
                raise Exception("Invalid response")

            raise Exception(message[1].strip())

        if req.status_code == 301:
            target = urljoin(self.url, req.headers['location'])
            if target.startswith(AMO_EDITOR_BASE):
                req = self.session.get(target, stream=True, allow_redirects=False)
            else:
                req.raise_for_status()

        return req

    def get_version_page(self, page=1):
        req = self.session.get(self.url + "?page=%d" % page, stream=True, allow_redirects=False)
        req = self.check_redirects(req)

        req.raw.decode_content = True
        doc = lxml.html.parse(req.raw).getroot()

        namenodes = doc.xpath(csspath('h2.addon span:first-of-type'))
        self.addonname = namenodes[0].text.strip().replace("Review ", "", 1)

        self.token = doc.xpath(csspath('form input[name="csrfmiddlewaretoken"]'))[0].attrib['value']
        self.enabledversions = [
          x.attrib['value'] for x in doc.xpath(csspath('#id_versions > option'))
        ]

        self.addonid = doc.xpath(csspath('#addon'))[0].attrib['data-id']
        try:
            slugnodes = doc.xpath(csspath(".file-info > .light > a:not([title])"))
            self.slug = unquote(slugnodes[0].attrib['href'].split("/")[-4])
        except IndexError:
            slugnodes = doc.xpath(csspath("#actions-addon > li > a[href$='/edit']"))
            self.slug = unquote(slugnodes[0].attrib['href'].split("/")[-4])

        if self.unlisted:
            self.url = '%s/review-unlisted/%s' % (AMO_EDITOR_BASE, self.slug)
        else:
            self.url = '%s/review-listed/%s' % (AMO_EDITOR_BASE, self.slug)

        self.actions = [
            i.attrib['value'] for i in doc.xpath(csspath('[name="action"]'))
        ]

        downloadnodes = doc.xpath('//strong[@class="downloads"]')
        self.downloads = 0
        if len(downloadnodes) > 0:
            self.downloads = int(downloadnodes[0].text.replace(",", ""))

        self.adu = int(downloadnodes[1].text.replace(",", "")) if len(downloadnodes) > 1 else 0

        first_page_path = ".review-files-paginate > .pagination > li > strong:first-of-type, " + \
            "#review-files-paginate > .pagination > li > strong:first-of-type"
        first_page_node = doc.xpath(csspath(first_page_path))
        is_first_page = first_page_node[0].text == "1" if len(first_page_node) > 0 else True

        if page > 1 and is_first_page:
            # We've gone over the last page, need to bail early
            return False

        self.versionmap = {}
        options = doc.xpath(csspath('#id_versions option'))
        for option in options:
            self.versionmap[option.text] = option.attrib['value']

        heads = doc.xpath(
          csspath('.review-files > .listing-header, #review-files > .listing-header')
        )

        versions = []
        for head in heads:
            versions.append(AddonReviewVersion(self, head, head.getnext()))

        self.versions = versions + self.versions

        devnodes = doc.xpath(
          csspath('#scroll_sidebar ul:not([id]) a[href*="/user/"]')
        )

        for dev in devnodes:
            self.developers.append(User.getcache(self.parent, dev.attrib['href'].split("/")[-2]))

        self.page = page
        return True

    def get_all_versions(self):
        incomplete = True
        while incomplete:
            incomplete = self.get_next_page()
        return self.versions

    def get_versions_until(self, func, default=None):
        res = default
        while True:
            res = func(self.versions, self.page)
            if res is not False:
                return res

            if not self.get_next_page():
                return default
        return res

    def get_enabled_version_numbers(self):
        return self.enabledversions

    def decide(self, action, comments, versions=None, versionids=None):
        versionids = versionids or []
        versions = versions or []
        if len(versions) > 0:
            if action == 'reject_multiple_versions':
                versionids = [v.id for v in versions if v.id]
            else:
                versionids = []

        postdata = {
            'csrfmiddlewaretoken': self.token,
            'action': action,
            'comments': comments,
            'applications': '',  # TODO
            'operating_systems': '',  # TODO
            'info_request': 'sometime in the past',
            'info_request_deadline': 7,
            'versions': versionids
        }
        headers = {
            'referer': self.url
        }

        req = self.session.post(self.url, data=postdata, headers=headers)
        return req.status_code == 200

    def flags(self, flags=None):
        url = AMO_REVIEWERS_API_BASE + '/addon/%s/flags/' % self.addonid
        headers = {'Authorization': 'Session ' + self.session.cookies.get('sessionid')}
        req = self.session.patch(url, json=flags or {}, headers=headers, allow_redirects=False)
        print(req.json())
        if not req.status_code == 200:
            raise Exception("Request error %d" % req.status_code)
        return req.json()

    def admin_disable(self):
        url = AMO_REVIEWERS_API_BASE + '/addon/%s/disable/' % self.addonid
        headers = {'Authorization': 'Session ' + self.session.cookies.get('sessionid')}
        req = self.session.post(url, headers=headers, allow_redirects=False)
        return req.status_code == 202

    def remove_extra_delay(self):
        flags = self.flags({"auto_approval_delayed_until": None})
        return flags["auto_approval_delayed_until"] is None

    def set_next_autoapproval(self, value=True):
        key = "auto_approval_disabled_until_next_approval"
        if self.unlisted:
            key += "_unlisted"
        flags = self.flags({key: None})
        return flags[key] == value

    def subscription(self, subscribe=True):
        url = AMO_REVIEWERS_API_BASE + '/addon/{}/{}subscribe_{}listed/'.format(
            self.addonid,
            "un" if not subscribe else "",
            "un" if self.unlisted else ""
        )
        headers = {'Authorization': 'Session ' + self.session.cookies.get('sessionid')}
        req = self.session.post(url, headers=headers, allow_redirects=False)
        return req.status_code == 202


class AddonReviewVersion:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, parent, head, body):
        self.parent = parent
        self.session = parent.session

        self.id = None
        self.sources = None
        self.sourcepath = None
        self.sourcefilename = None
        self.version = None
        self.files = []
        self.apps = []

        self._init_head(head)
        self._init_body(body)

    def _init_head(self, head):
        args = next(head.iterchildren()).text.strip().split(" ")
        _, self.version, _, month, day, year = [_f for _f in args if _f]
        self.date = '%s %s %s' % (month, day, year)

        lights = head.xpath(csspath("th .light"))
        self.confirmed = len(lights) > 1 and lights[1].text == "(Confirmed)"

        # This will work for non-deleted files, and is better for multiple files per version
        self.id = None
        if self.version in self.parent.versionmap:
            self.id = self.parent.versionmap[self.version]

    def _init_body(self, body):
        fileinfo = body.xpath(csspath('.file-info'))
        for info in fileinfo:
            self.files.append(AddonVersionFile(self, info))

        # This is the fallback to determine the id for deleted add-ons
        codemgr = fileinfo[0].xpath(csspath("a[href^='https://code.addons.mozilla.org']"))
        if codemgr and not self.id:
            self.id = codemgr[0].attrib['href'].split("/")[-2]

        sourcelink = body.xpath(csspath('.files > div > a[href]'))
        if len(sourcelink) > 0:
            self.sources = urljoin(AMO_EDITOR_BASE, sourcelink[0].attrib['href'])

        appnodes = body.xpath(csspath('.files > ul > li > .app-icon'))
        if len(appnodes) > 0:
            appre = re.compile(r'ed-sprite-(\w+)')
            for node in appnodes:
                matches = appre.search(node.attrib['class'])
                if matches:
                    self.apps.append(matches.group(1))

    def savesources(self, targetpath, chunksize=16384):
        if self.sources:
            req = self.session.get(self.sources, stream=True)

            _, params = cgi.parse_header(req.headers['content-disposition'])

            self.sourcefilename = params['filename']
            base, ext = os.path.splitext(params['filename'])
            if ext == ".gz":
                _, tarext = os.path.splitext(base)
                if tarext == ".tar":
                    ext = ".tar.gz"

            self.sourcepath = os.path.join(targetpath, self.version, "sources" + ext)
            sourcedir = os.path.dirname(self.sourcepath)
            if not os.path.exists(sourcedir):
                os.mkdir(sourcedir)

            with open(self.sourcepath, 'wb') as fd:
                for chunk in req.iter_content(chunksize):
                    fd.write(chunk)

    def extractsources(self, targetpath):
        if not self.sourcepath:
            self.savesources(targetpath)

        extractpath = os.path.join(targetpath, self.version, "src")

        if os.path.exists(extractpath):
            shutil.rmtree(extractpath)

        try:
            os.makedirs(extractpath)
        except OSError:
            pass

        mime = magic.from_file(self.sourcepath, mime=True)

        try:
            if mime == "application/x-7z-compressed":
                with SevenZFile(self.sourcepath, 'r') as zf:
                    zf.extractall(extractpath)
            elif mime == "application/zip":
                with ZipFile(self.sourcepath, 'r') as zf:
                    zf.extractall(extractpath)
            elif mime in ('application/x-gzip', 'application/gzip'):
                with tarfile.open(self.sourcepath, 'r:gz') as zf:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner=numeric_owner) 
                        
                    
                    safe_extract(zf, extractpath)
            else:
                print("Don't know how to handle %s, skipping extraction" % mime)
        except Exception:  # pylint: disable=broad-except
            os.rmdir(extractpath)
            traceback.print_exc()
            print("Could not extract sources due to above exception, skipping extraction")

    def linklatest(self, targetpath):
        dst = os.path.join(targetpath, "latest")
        if os.path.islink(dst):
            target = os.path.dirname(os.readlink(dst))
            if cmp_version(target, self.version) > 0:
                return
            os.unlink(dst)

        os.symlink(self.version + os.path.sep, dst)


class AddonVersionFile:
    # pylint: disable=too-many-instance-attributes

    OS_LABEL_TO_SHORTNAME = {
        'Linux': 'linux',
        'Mac OS X': 'mac',
        'Windows': 'windows',
        'All Platforms': 'all',
        'Download': 'all',  # Themes
        'Android': 'android'
    }

    def __init__(self, parent, fileinfo):
        self.parent = parent
        self.session = parent.session

        infourl = fileinfo.xpath(csspath('.reviewers-install'))
        self.url = infourl[0].attrib['href']
        self.platforms = [
            self.OS_LABEL_TO_SHORTNAME[platform]
            for platform in infourl[0].text.split(" / ")
        ]

        if len({"linux", "mac", "windows"} - set(self.platforms)) == 0:
            # This is close enough to "all"
            self.platforms = ["all"]

        statusdiv = fileinfo.xpath(csspath('.light > div'))
        self.status = statusdiv[0].text.strip()

        permnode = fileinfo.xpath(csspath(".file-permissions strong"))
        self.permissions = permnode[0].tail.strip() if len(permnode) > 0 else None

        urlpath = urlparse(self.url).path
        urlpathparts = urlpath.split('/')
        self.filename = urlpathparts[-1]
        self.fileid = urlpathparts[-3]
        self.savedpath = None
        self.profile = None

    def get(self):
        if self.savedpath:
            return open(self.savedpath, 'r')
        else:
            return self.session.get(self.url, stream=True)

    @property
    def _platformsuffix(self):
        return "-" + "-".join(self.platforms) if len(self.parent.files) > 1 else ""

    def extract(self, targetpath):
        if not self.savedpath:
            self.save(targetpath)

        if self.savedpath.endswith(".xml"):
            return

        xpidir = "xpi" + self._platformsuffix
        extractpath = os.path.join(targetpath, self.parent.version, xpidir)
        try:
            os.makedirs(os.path.dirname(extractpath))
        except OSError:
            pass

        try:
            with ZipFile(self.savedpath, 'r') as zf:
                zf.extractall(extractpath)
        except BadZipfile:
            print("Could not extract xpi, skipping")

    def save(self, targetpath, chunksize=16384):
        response = self.session.get(self.url, stream=True)

        if response.headers['content-type'] == "application/x-xpinstall":
            xpifile = "addon%s.xpi" % (self._platformsuffix)
        elif response.headers['content-type'].startswith("text/xml"):
            xpifile = "addon.xml"
        else:
            raise Exception("Unknown content type " + response.headers['content-type'])

        self.savedpath = os.path.join(targetpath, self.parent.version, xpifile)

        try:
            os.makedirs(os.path.dirname(self.savedpath))
        except OSError:
            pass

        with open(self.savedpath, 'wb') as fd:
            for chunk in response.iter_content(chunksize):
                fd.write(chunk)

    def createprofile(self, targetpath, delete=False):
        if not self.savedpath:
            self.save(targetpath)

        profiledir = "profile" + self._platformsuffix
        profilepath = os.path.join(targetpath, self.parent.version, profiledir)
        if delete and os.path.exists(profilepath):
            shutil.rmtree(profilepath)

        # TODO non-firefox, multiple files
        profileparams = {
            "profile": profilepath,
            "addons": [self.savedpath],
            "preferences": {
                "xpinstall.signatures.required": False,

                # Enable browser toolbox to monitor network requests
                "devtools.chrome.enabled": True,
                "devtools.debugger.remote-enabled": True
            },
            "restore": False
        }
        self.profile = FirefoxProfile(**profileparams)
        return self.profile
