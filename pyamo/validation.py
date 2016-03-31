# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

from __future__ import print_function

from .utils import flagstr, AMO_DEVELOPER_BASE
from urlparse import urljoin
from HTMLParser import HTMLParser
from textwrap import TextWrapper
from collections import defaultdict

class ValidationReport(object):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, addonid, report, platform='all'):
        self.reportid = report['upload']
        self.report_url = urljoin(AMO_DEVELOPER_BASE, report['full_report_url'])

        self.addonid = addonid
        self.metadata = defaultdict()
        self.platform = platform

        self.compat = defaultdict()
        self.errors = self.warnings = self.notices = 0

        self.failure = report['error']
        self.completed = self.success and isinstance(report['validation'], dict)

        if self.completed:
            self.completed = True
            validation = report['validation']
            self.metadata = validation['metadata']

            self.compat = validation['compatibility_summary']
            self.signing = validation['signing_summary']
            self.messages = validation['messages']


            self.errors = validation['errors']
            self.warnings = validation['warnings']
            self.notices = validation['notices']

    @property
    def success(self):
        return self.errors == 0 and not self.failure

    @property
    def name(self):
        return self.metadata['name']

    @property
    def version(self):
        return self.metadata['version']

    def show_messages(self, level='all'):
        levels = {'error': 0, 'warning': 1, 'notice': 2, 'all': 3}
        if not self.completed:
            return

        parser = HTMLParser()
        wrapper = TextWrapper(initial_indent='\t', subsequent_indent='\t', width=120)
        for message in self.messages:
            if levels[message['type']] > levels[level]:
                continue

            msgtype = message['type'][0].upper() + message['type'][1:]

            print("%s: %s" % (msgtype, message['message']))
            print(wrapper.fill(parser.unescape("".join(message['description']))) + "\n")

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __unicode__(self):
        if not self.completed:
            res = "Validation in progress for %s\n" % self.addonid
            res += "Full report at %s" % self.report_url
        elif not self.success:
            res = "Validation failed for %s\n" % self.addonid
            res += "Full report at %s\n" % self.report_url
            res += "%d validation messages" % len(self.messages)
        else:
            res = "Validation %s for %s %s %s%s\n" % (
                'complete' if self.success else 'errored',
                self.name, self.version,
                flagstr(self.metadata, "contains_binary_extension", "binary"),
                flagstr(self.metadata, "requires_chrome")
            )
            res += "Total %d errors, %d warnings, %d notices\n" % (
                self.errors, self.warnings, self.notices
            )
            res += "Full report at %s\n" % self.report_url

            res += "Compatibility %d notices, %d warnings, %d errors\n" % (
                self.compat['notices'], self.compat['warnings'], self.compat['errors']
            )

            res += "Signing %d trivial, %d low, %d medium, %d high\n" % (
                self.signing['trivial'], self.signing['low'],
                self.signing['medium'], self.signing['high']
            )

            res += "%d validation messages" % len(self.messages)

        return res
