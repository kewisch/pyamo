#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015

import os
from setuptools import setup
from setuptools.config import read_configuration

cfg = read_configuration(os.path.join(os.path.dirname(__file__), 'setup.cfg'))
cfg["options"].update(cfg["metadata"])
cfg=cfg["options"]
setup(use_scm_version = True, **cfg)
