# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

from __future__ import print_function

import os
import json
import pickle

import lxml.html
import requests

from .utils import AMO_BASE, AMO_API_BASE, AMO_ADMIN_BASE, FXASession


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
            with os.fdopen(os.open(self.cookiefile, os.O_WRONLY | os.O_CREAT, 0o600), 'w') as fdr:
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
        old_login_url = '%s/firefox/users/login' % AMO_BASE
        oauth_login_slice = 'v1/authorization'

        target_url = req.headers['location'] if req.status_code == 302 else req.url
        islogin = target_url.startswith(old_login_url) or oauth_login_slice in target_url

        loginsuccess = False
        doc = None

        while islogin and not loginsuccess:
            if doc is not None:
                if req.raw:
                    req.raw.decode_content = True
                    doc = lxml.html.parse(req.raw).getroot()
                else:
                    doc = lxml.html.fromstring(req.content)

            if self.loginfail > 2 or not self.login_prompter:
                raise requests.exceptions.HTTPError(401)
            self.loginfail += 1

            print("Incorrect user/password or session expired")

            loginsuccess = self.login(doc)

        return not islogin

    def login(self, logindoc=None):
        self.cookies.clear_expired_cookies()

        if logindoc is None:
            req = super(AmoSession, self).request('get',
                                                  '%s/firefox/users/login' % AMO_BASE,
                                                  stream=True)
            req.raw.decode_content = True
            logindoc = lxml.html.parse(req.raw).getroot()

        fxaconfig = json.loads(logindoc.body.attrib['data-fxa-config'])
        api_host = fxaconfig['oauthHost'].replace('oauth', 'api')

        with FXASession(api_host, fxaconfig, self.login_prompter) as session:
            code = session.authorize_code()

            redirdata = {
                # The second part of the state is /en-US/firefox in base64
                'state': "%s:L2VuLVVTL2ZpcmVmb3gv" % fxaconfig['state'],
                'action': 'signin',
                'code': code
            }

            req = super(AmoSession, self).request('get',
                                                  '%s/accounts/authenticate/' % AMO_API_BASE,
                                                  params=redirdata, allow_redirects=False)

        return req.status_code == 302
