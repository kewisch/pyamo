# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import os
import pickle

import lxml.html
import requests

from .utils import AMO_BASE

class AmoSession(requests.Session):
    def __init__(self, service, login_prompter, cookiefile=None, *args, **kwargs):
        self.service = service
        self.login_prompter = login_prompter
        self.loginfail = 0
        super(AmoSession, self).__init__(*args, **kwargs)
        self.load(cookiefile)

    def load(self, cookiefile):
        self.cookiefile = cookiefile
        if self.cookiefile:
            try:
                with open(cookiefile) as fdr:
                    cookies = requests.utils.cookiejar_from_dict(pickle.load(fdr))
                    self.cookies = cookies
            except IOError, _:
                pass

    def persist(self):
        if self.cookiefile:
            with os.fdopen(os.open(self.cookiefile, os.O_WRONLY | os.O_CREAT, 0600), 'w') as fdr:
                pickle.dump(requests.utils.dict_from_cookiejar(self.cookies), fdr)

    def request(self, method, url, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (10.0, 10.0)

        while True:
            req = super(AmoSession, self).request(method, url, *args, **kwargs)
            req.raise_for_status()
            if self.check_login_succeeded(req):
                return req

    def check_login_succeeded(self, req):
        login_url = '%s/firefox/users/login' % AMO_BASE
        if req.status_code == 302:
            islogin = req.headers['location'].startswith(login_url)
        else:
            islogin = req.url.startswith(login_url)

        loginsuccess = False
        doc = None

        while islogin and not loginsuccess:
            if doc is not None:
                if req.raw:
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
            logindoc = lxml.html.parse(req.raw).getroot()

        username, password = self.login_prompter()

        postdata = {
            'username': username,
            'password': password,
            'rememberme': 'on'
        }
        for form in logindoc.forms:
            if 'csrfmiddlewaretoken' in form.inputs:
                postdata['csrfmiddlewaretoken'] = form.inputs['csrfmiddlewaretoken'].value
                break

        req = super(AmoSession, self).request('post',
                                              '%s/firefox/users/login' % AMO_BASE,
                                              data=postdata, allow_redirects=False)
        return req.status_code == 302

