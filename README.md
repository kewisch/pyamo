pyamo - addons.mozilla.org for python
=====================================

These tools provide some classes and a command line tool to access addons.mozilla.org. This site
doesn't have a services API, therefore these tools use website scraping to determine the right
information and use the same endpoints as they would be used in the browser.

The command line tool is installed under the name `amo` and has the following commands available:

    info          Show basic information about an add-on
    list          List add-ons in the given queue
    get           Download one or more versions of an add-on, including sources
    run           Run an add-on in Firefox (preferably in a VM)
    decide        Make a review decision for an add-on, along with message
    logs          Show the review logs

    upload        Upload an add-on to addons.mozilla.org

    adminget      Show admin manage information about an add-on
    adminchange   Change the status of an add-ons and its files using the admin manage page
    admindisable  Admin disable one or more add-ons, optionally with a rejection message

Configuration
-------------
The amo utility supports setting some configuration values. The file needs to be placed in
`~/.amorc` on Unix, or `%HOME%/amorc.ini` on Windows.

The `[defaults]` section allows to configure defaults for optional arguments. Here are some
examples:

```ini
[defaults]
out = --outdir ~/path/to/amofolder --binary ~/path/to/run_in_vm.py
run = --outdir ~/path/to/amofolder --binary ~/path/to/run_in_vm.py
logs = -k reviewer
decide = -f
```

It is highly recommended to set a the `--outdir` argument as default, to make
sure all add-ons end up in the same folder.

The `[auth]` section allows to specify an authentication key for redash, which is only necessary for
admin commands.

```init
[auth]
redash_key=42c85d86fd212538f4394f47c80fa62c
```

Examples
--------

### amo upload
Upload one or more xpi packages. Typical usage is specifying the add-on id, together with one or
more occurrences of the -x parameter for each platform. Example:

```
amo upload lightning \
    -x linux lightning-linux.xpi \
    -x mac lightning-mac.xpi \
    -x win lightning-win32
```

### amo get
Downloads one or more versions to the hard drive for review. Will download both the xpi and the
sources and once done extract each package. The files will be saved in a sub-directory named after
the addon id in the current (or specified) directory.

When specifying version numbers you can also use the tag `latest` to retrieve the latest version and
the `previous` tag to get the last accepted version. This is useful when specifying multiple
versions to download.

A commonly used option is the diff option `-d`, which automatically gets the latest and previous
versions. This is useful to compare versions.

Example:

```
amo get -d lightning
```
