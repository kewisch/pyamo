# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import cssselect
import os
from pytz import timezone

# set AMO_HOST=adddons.allizom.org to use staging
AMO_HOST = os.environ['AMO_HOST'] if 'AMO_HOST' in os.environ else 'addons.mozilla.org'

AMO_BASE = "https://%s/en-US" % AMO_HOST
AMO_EDITOR_BASE = '%s/editors' % AMO_BASE
AMO_TIMEZONE = timezone("America/Los_Angeles")

def csspath(query):
    return cssselect.HTMLTranslator().css_to_xpath(query)
