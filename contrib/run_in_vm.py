#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# Portions Copyright (C) Philipp Kewisch, 2016

import os.path
import sys
import subprocess
import psutil

# Windows path where reviews shared folder is mounted
REVIEW_BASE_VM = os.environ.get("AMO_VMDRIVE", "E:")

# Path where reviews are kept locally, usually the cwd
REVIEW_BASE_HOST = os.environ.get("AMO_REVIEWPATH", os.path.abspath(os.getcwd()))

# Execubtable path for VBoxManage
VBOXMANAGE = os.environ.get("VBOXMANAGE", "VBoxManage")

# The VM to start and user/password
VMNAME = os.environ.get("AMO_VMNAME", "IE10 - Win7")
VMUSER = os.environ.get("AMO_VMUSER", "IEUser")
VMPASS = os.environ.get("AMO_VMPASS", "Passw0rd!")

# Path to Firefox on the VM
FXPATH = os.environ.get("AMO_VMFXPATH", "C:/Program Files/Firefox/firefox.exe")

# Start page to show
STARTPAGE = os.environ.get("AMO_VMSTARTPAGE", "about:addons")

# --- end configurable options ---

def adapt_path(path):
    return REVIEW_BASE_VM + "/" + \
        os.path.relpath(path, os.path.expanduser(REVIEW_BASE_HOST))

def filter_args(args):
    for index, arg in enumerate(args):
        if arg == "-profile":
            args[index+1] = adapt_path(args[index+1])
            break
    return args

def stripn(string):
    return string.replace("\n", " ")

def find_parent_process(name, process=psutil.Process(os.getpid())):
    if not process or process.name == name:
        return process
    return find_parent_process(name, process.parent)

def focus_title(title):
    if sys.platform == "darwin":
        os.system(stripn('''/usr/bin/osascript -e 'tell app "Finder" to
                         set frontmost of process "%s" to true' ''' % title))
def focus_pid(pid):
    if sys.platform == "darwin":
        os.system(stripn('''/usr/bin/osascript -e 'tell application "System Events" to
                         set frontmost of the first process
                         whose unix id is %d to true' ''' % pid))

def main():
    fxargs = filter_args(sys.argv)
    vboxargs = [VBOXMANAGE, "guestcontrol", VMNAME, "run",
                "--username", VMUSER, "--password", VMPASS,
                "--exe", FXPATH, "--", FXPATH] + fxargs[1:] + [STARTPAGE]

    focus_title("VirtualBoxVM")
    subprocess.call(vboxargs)
    terminal = find_parent_process("Terminal")
    if terminal:
        focus_pid(terminal.pid)

main()
