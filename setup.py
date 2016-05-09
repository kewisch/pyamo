# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import os
from setuptools import setup

setup(
    name = "pyamo",
    version = "1.0.0",
    author = "Philipp Kewisch",
    author_email = "mozilla@kewis.ch",
    description = ("Access services on addons.mozilla.org from python"),
    license = "MPL-2.0",
    keywords = "amo mozilla add-ons",
    url = "https://github.com/kewisch/pyamo",
    packages = ['pyamo'],
    install_requires = [
        'PyFxA',
        'python-magic',
        'requests',
        'lxml',
        'cssselect',
        'arghandler >=1.0.3',
        'pylzma',
        'pytz',
        'tzlocal',
        'python-dateutil'
    ],
    entry_points = {
        'console_scripts': ['amo=pyamo.cli:main']
    },
    classifiers = [
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Topic :: Utilities",
    ]
)
