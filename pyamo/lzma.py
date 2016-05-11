# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

from __future__ import print_function

import os

from py7zlib import Archive7z


class SevenZFile(object):
    # pylint: disable=too-few-public-methods

    def __init__(self, filepath, mode='rb'):
        self.fd = open(filepath, mode)
        self.archive = Archive7z(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, vtype, value, traceback):
        if self.fd:
            self.fd.close()

    def extractall(self, path):
        for name in self.archive.getnames():
            outfilename = os.path.join(path, name)
            outdir = os.path.dirname(outfilename)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            outfile = open(outfilename, 'wb')
            outfile.write(self.archive.getmember(name).read())
            outfile.close()
