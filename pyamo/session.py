# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

from __future__ import print_function

import os
import pickle

import urlparse
import requests

from .utils import AMO_API_BASE, AMO_ADMIN_BASE, FXASession


class AmoSession(requests.Session):
    def __init__(self, service, login_prompter, cookiefile=None, *args, **kwargs):
        self.service = service
        self.login_prompter = login_prompter
        self.loginfail = 0
        self.timeout = None
        super(AmoSession, self).__init__(*args, **kwargs)
        self.load(cookiefile)

    def load(self, cookiefile):
        self.cookiefile = cookiefile
        if self.cookiefile:
            try:
                with open(cookiefile) as fdr:
                    cookies = requests.utils.cookiejar_from_dict(pickle.load(fdr))
                    self.cookies = cookies
            except IOError:
                pass

    def persist(self):
        if self.cookiefile:
            with os.fdopen(os.open(self.cookiefile, os.O_WRONLY | os.O_CREAT, 0600), 'w') as fdr:
                pickle.dump(requests.utils.dict_from_cookiejar(self.cookies), fdr)

    def request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            if self.timeout:
                kwargs['timeout'] = (self.timeout, self.timeout)
            elif url.startswith(AMO_ADMIN_BASE):
                kwargs['timeout'] = (2.0, 2.0)
            else:
                kwargs['timeout'] = (10.0, 10.0)

        while True:
            req = super(AmoSession, self).request(method, url, *args, **kwargs)
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
        req = super(AmoSession, self).request('get', login_url, allow_redirects=False)

        if req.status_code != 302:
            return False

        urlparts = urlparse.urlparse(req.headers['Location'])
        query = urlparse.parse_qs(urlparts.query)
        scope = query['scope'][0]
        client_id = query['client_id'][0]
        origin = 'https://' + urlparts.hostname

        with FXASession(origin, scope, client_id, self.login_prompter) as session:
            code = session.authorize_code()

            redirdata = {
                'config': 'amo',
                'code': code,
                'state': query['state'][0],
                'action': 'signin'
            }

            req = super(AmoSession, self).request('get',
                                                  query['redirect_url'][0],
                                                  params=redirdata, allow_redirects=False)

        return req.status_code == 302
