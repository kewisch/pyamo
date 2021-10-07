# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

import os
import json

import urllib.parse
import requests

from .utils import AMO_API_BASE, AMO_API_AUTH, AMO_ADMIN_BASE, FXASession


class AmoSession(requests.Session):
    def __init__(self, service, login_prompter, *args, cookiefile=None, **kwargs):
        self.service = service
        self.login_prompter = login_prompter
        self.loginfail = 0
        self.timeout = None
        super().__init__(*args, **kwargs)
        self.load(cookiefile)

    def load(self, cookiefile):
        self.cookiefile = cookiefile
        if self.cookiefile:
            try:
                with open(cookiefile) as fdr:
                    try:
                        self.cookies = requests.utils.cookiejar_from_dict(json.load(fdr))
                    except Exception:  # pylint: disable=broad-except
                        self.cookes = {}
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

            loginsuccess = self.login()

        return not islogin

    def login(self):
        self.cookies.clear_expired_cookies()

        login_url = '%s/accounts/login/start/?config=amo&to=/en-US/firefox/' % AMO_API_BASE
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
