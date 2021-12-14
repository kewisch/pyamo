# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import os
import json

import urllib.parse
import sqlite3
import http
import shutil
import webbrowser
import tempfile

import requests

from .utils import AMO_API_BASE, AMO_API_AUTH, AMO_ADMIN_BASE, FXASession, fxprofile


class AmoSession(requests.Session):
    def __init__(self, service, login_prompter, *args, **kwargs):
        self.service = service
        self.login_prompter = login_prompter
        self.loginfail = 0
        self.timeout = None
        self.cookiefile = None
        self.firefox_cookies_profile = None
        super().__init__(*args, **kwargs)

    def load_firefox_cookies(self, profile):
        self.cookiefile = None
        self.firefox_cookies_profile = profile
        self.cookies = http.cookiejar.CookieJar()

        with tempfile.TemporaryDirectory() as tempdir:
            tempsql = os.path.join(tempdir, "cookies.sqlite")
            shutil.copyfile(fxprofile(self.firefox_cookies_profile) / "cookies.sqlite", tempsql)
            conn = sqlite3.connect(tempsql)
            cursor = conn.cursor()
            cursor.execute("SELECT host, path, isSecure, expiry, name, value FROM moz_cookies")
            for item in cursor.fetchall():
                domain_spec = item[0].startswith('.')
                cookie = http.cookiejar.Cookie(0, item[4], item[5],
                                               None, False,
                                               item[0], domain_spec, domain_spec,
                                               item[1], False,
                                               item[2],
                                               item[3], item[3] == "",
                                               None, None, {})
                self.cookies.set_cookie(cookie)
            conn.close()

    def load(self, cookiefile):
        self.firefox_cookies_profile = None
        self.cookiefile = cookiefile
        try:
            with open(cookiefile) as fdr:
                try:
                    self.cookies = requests.utils.cookiejar_from_dict(json.load(fdr))
                except Exception:  # pylint: disable=broad-except
                    self.cookies = {}
        except IOError:
            pass

    def persist(self):
        if self.cookiefile:
            mode = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            with os.fdopen(os.open(self.cookiefile, mode, 0o600), 'w') as fdr:
                json.dump(requests.utils.dict_from_cookiejar(self.cookies), fdr)

    def request(self, method, url, **kwargs):  # pylint: disable=arguments-differ
        if 'timeout' not in kwargs:
            if self.timeout:
                kwargs['timeout'] = (self.timeout, self.timeout)
            elif url.startswith(AMO_ADMIN_BASE):
                kwargs['timeout'] = (2.0, 2.0)
            else:
                kwargs['timeout'] = (10.0, 10.0)

        while True:
            req = super().request(method, url, **kwargs)
            req.raise_for_status()
            if self.check_login_succeeded(req):
                return req

    def check_login_succeeded(self, req):
        target_url = req.headers['location'] if req.status_code == 302 else req.url
        islogin = target_url.endswith("users/login") or "v1/authorization" in target_url

        loginsuccess = False

        while islogin and not loginsuccess:
            if self.loginfail > 2 or not self.login_prompter:
                raise requests.exceptions.HTTPError(401)
            self.loginfail += 1

            print("Incorrect user/password or session expired")

            self.cookies.clear()
            loginsuccess = self.login()

        return not islogin

    def login(self):
        login_url = '%s/accounts/login/start/?config=amo&to=/en-US/firefox/' % AMO_API_BASE

        self.cookies.clear_expired_cookies()
        if self.firefox_cookies_profile:
            webbrowser.open_new_tab(login_url)
            input("Log in to AMO in Firefox and press enter to continue")
            self.load_firefox_cookies(self.firefox_cookies_profile)
            return True

        req = super().request('get', login_url, allow_redirects=False)

        if req.status_code != 302:
            return False

        urlparts = urllib.parse.urlparse(req.headers['Location'])
        query = urllib.parse.parse_qs(urlparts.query)
        scope = query['scope'][0]
        client_id = query['client_id'][0]
        origin = 'https://' + urlparts.hostname

        with FXASession(origin, scope, client_id, self.login_prompter) as session:
            code = session.authorize_code()

            redirdata = {
                'code': code,
                'state': query['state'][0],
                'action': 'signin'
            }

            redirect_url = "%s/authenticate-callback/" % AMO_API_AUTH
            req = super().request('get', redirect_url, params=redirdata, allow_redirects=False)

        return req.status_code == 302
