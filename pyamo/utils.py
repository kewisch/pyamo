# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2015-2016

from __future__ import print_function

import os
import re
import sys

from ConfigParser import ConfigParser, NoOptionError, NoSectionError
from pytz import timezone
from mozrunner import FirefoxRunner

import argparse
import cssselect
import fxa.core
import fxa.oauth
import fxa.errors

# set AMO_HOST=adddons.allizom.org to use staging
AMO_HOST = os.environ['AMO_HOST'] if 'AMO_HOST' in os.environ else 'addons.mozilla.org'

AMO_BASE = "https://%s/en-US" % AMO_HOST
AMO_API_BASE = "https://%s/api/v3" % AMO_HOST
AMO_EDITOR_BASE = 'https://reviewers.%s/en-US/reviewers' % AMO_HOST
AMO_ADMIN_BASE = '%s/admin' % AMO_BASE
AMO_DEVELOPER_BASE = '%s/developers' % AMO_BASE
AMO_TIMEZONE = timezone("America/Los_Angeles")

VALIDATION_WAIT = 5
RE_VERSION_BETA = re.compile(r"""(a|alpha|b|beta|pre|rc) # Either of these
                              (([\.-]\d)?\d*)         # followed by nothing
                              $                       # or 123 or .123 or -123
                              """, re.VERBOSE)

UPLOAD_PLATFORM = {
    'all': '1',
    'linux': '2',
    'osx': '3',
    'mac': '3',
    'windows': '5',
    'win': '5',
    'win32': '5',
    'android': '7'
}


def csspath(query):
    return cssselect.HTMLTranslator().css_to_xpath(query)


def flagstr(obj, name, altname=None):
    if name in obj and obj[name]:
        return "[%s]" % (altname or name)
    else:
        return ""


class FXASession(object):
    # pylint: disable=too-few-public-methods
    def __init__(self, api_url, fxaconfig, login_prompter):
        self.scope = fxaconfig['scope']
        self.client_id = fxaconfig['clientId']
        self.login_prompter = login_prompter

        self.client = fxa.core.Client(server_url=api_url)
        self.oauth_client = fxa.oauth.Client(server_url=fxaconfig['oauthHost'])
        self.session = None

    def __enter__(self):
        username, password = self.login_prompter()

        try:
            self.session = self.client.login(username, password)
        except fxa.errors.ClientError, e:
            if e.error == "Request blocked":
                self.client.send_unblock_code(username)
                code = self.login_prompter(unblock_code=True)
                self.session = self.client.login(username, password, unblock_code=code)
            else:
                raise e

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.destroy_session()
        self.session = None
        return False

    def authorize_code(self):
        return self.oauth_client.authorize_code(self.session, self.scope, self.client_id)


def parse_args_with_defaults(handler, cmd, args):
    config = ConfigParser()
    if sys.platform.startswith("win"):
        configfilepath = os.path.expanduser("~/amorc.ini")
    else:
        configfilepath = os.path.expanduser('~/.amorc')
    config.read(configfilepath)

    # Read the defaults from the config file, if it does not exist just parse
    # options as usual.
    try:
        defaults = config.get('defaults', cmd).split(" ")
    except (NoOptionError, NoSectionError):
        return handler.parse_args(args)

    # Create an argument parser that takes just the options, but no defaults or
    # requirements.  Setting the kwargs is a bit fragile, but since we can't
    # just copy an ArgumentParser this is the best alternative.
    defhandler = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    for action in handler._actions:  # pylint: disable=protected-access
        if action.option_strings:
            kwargs = {"action": action.__class__}
            if action.nargs:
                kwargs['nargs'] = action.nargs
            if action.choices:
                kwargs['choices'] = action.choices

            defhandler.add_argument(*action.option_strings, **kwargs)

    # Parse the found defaults with this argument parser and use them as
    # defaults for the real handler.
    defargs = defhandler.parse_args(defaults)
    handler.set_defaults(**vars(defargs))
    return handler.parse_args(args)


def find_in_path(filename, path=os.environ['PATH']):
    dirs = path.split(os.pathsep)
    for dirname in dirs:
        if os.path.isfile(os.path.join(dirname, filename)):
            return os.path.join(dirname, filename)
        if os.name == 'nt' or sys.platform == 'cygwin':
            if os.path.isfile(os.path.join(dirname, filename + ".exe")):
                return os.path.join(dirname, filename + ".exe")
    return None


# pylint: disable=too-many-locals,too-many-branches
def find_binary(name):
    """Finds the binary path"""
    # Code taken from an old mozrunner

    app_name = name[0].upper() + name[1:]
    binary = None
    if sys.platform in ('linux2', 'sunos5', 'solaris') \
            or sys.platform.startswith('freebsd'):
        binary = find_in_path(name)
    elif os.name == 'nt' or sys.platform == 'cygwin':

        # find the default executable from the windows registry
        try:
            import _winreg
        except ImportError:
            pass
        else:
            sam_flags = [0]
            # KEY_WOW64_32KEY etc only appeared in 2.6+, but that's OK as
            # only 2.6+ has functioning 64bit builds.
            if hasattr(_winreg, "KEY_WOW64_32KEY"):
                if "64 bit" in sys.version:
                    # a 64bit Python should also look in the 32bit registry
                    sam_flags.append(_winreg.KEY_WOW64_32KEY)
                else:
                    # possibly a 32bit Python on 64bit Windows, so look in
                    # the 64bit registry incase there is a 64bit app.
                    sam_flags.append(_winreg.KEY_WOW64_64KEY)
            for sam_flag in sam_flags:
                try:
                    # assumes self.app_name is defined, as it should be for
                    # implementors
                    keyname = r"Software\Mozilla\Mozilla %s" % app_name
                    sam = _winreg.KEY_READ | sam_flag
                    app_key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, keyname, 0, sam)
                    version, _ = _winreg.QueryValueEx(app_key, "CurrentVersion")
                    version_key = _winreg.OpenKey(app_key, version + r"\Main")
                    path, _ = _winreg.QueryValueEx(version_key, "PathToExe")
                    return path
                except _winreg.error:
                    pass

        # search for the binary in the path
        binary = find_in_path(name)
        if sys.platform == 'cygwin':
            program_files = os.environ['PROGRAMFILES']
        else:
            program_files = os.environ['ProgramFiles']

        if binary is None:
            binpaths = [
                (program_files, 'Mozilla Firefox', 'firefox.exe'),
                (os.environ.get("ProgramFiles(x86)"), 'Mozilla Firefox', 'firefox.exe'),
                (program_files, 'Nightly', 'firefox.exe'),
                (os.environ.get("ProgramFiles(x86)"), 'Nightly', 'firefox.exe'),
                (program_files, 'Aurora', 'firefox.exe'),
                (os.environ.get("ProgramFiles(x86)"), 'Aurora', 'firefox.exe')
            ]
            for binpath in binpaths:
                path = os.path.join(*binpath)
                if os.path.isfile(path):
                    binary = path
                    break
    elif sys.platform == 'darwin':
        # Look for the application bundle in the user's home directory
        # or the system-wide /Applications directory.  If we don't find
        # it in one of those locations, we move on to the next possible
        # bundle name.
        appdir = os.path.join("~/Applications/%s.app" % app_name)
        if not os.path.isdir(appdir):
            appdir = "/Applications/%s.app" % app_name
        if os.path.isdir(appdir):
            # Look for a binary with any of the possible binary names
            # inside the application bundle.
            binpath = os.path.join(appdir,
                                   "Contents/MacOS/%s-bin" % name)
            if os.path.isfile(binpath):
                binary = binpath

    if binary is None:
        raise Exception('Could not locate your binary, you will need to set it.')
    return binary


def runprofile(binary, fileobj):
    try:
        runner = FirefoxRunner(binary=binary, profile=fileobj.profile)
        runner.start()
        runner.wait()
    except KeyboardInterrupt:
        pass
