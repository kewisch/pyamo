pyamo - addons.mozilla.org for python
=====================================

These tools provide some classes and a command line tool to access
addons.mozilla.org. This site doesn't have a services API, therefore these
tools use website scraping to determine the right information and use the same
endpoints as they would be used in the browser.


amo - the command line utility
------------------------------

General usage as follows, in most cases you don't have to use any of these
options, just the sub-commands:

```
usage: amo [-h] [-c COOKIES] [-d {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
           {info,run,logs,get,list,upload,decide} ...

positional arguments:
  {info,run,logs,get,list,upload,decide}
  cargs                 arguments for the subcommand

optional arguments:
  -h, --help            show this help message and exit
  -c COOKIES, --cookies COOKIES
                        the file to save the session cookies to
  -d {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --debug {DEBUG,INFO,WARNING,ERROR,CRITICAL}
```

### Configuration
The amo utility supports setting some configuration values. The file
needs to be placed in `~/.amorc` on unix, or `%HOME%/amorc.ini` on Windows.

Currently the only configuration is being able to specify defaults for the
subcommands, which is done in the `[defaults]` section. You can only specify
defaults for optional arguents. Here are some examples:

```ini
[defaults]
out = --outdir ~/path/to/amofolder --binary ~/path/to/run_in_vm.py
run = --outdir ~/path/to/amofolder --binary ~/path/to/run_in_vm.py
logs = -k reviewer
decide = -f
```

It is highly recommended to set a the `--outdir` argument as default, to make
sure all add-ons end up in the same folder.

### Developer commands
These commands are meant for add-on developers and will work for add-ons you
have developer access to.

#### amo upload
Uploads one or more xpi packages to an existing add-on. Typical usage is
specifying the add-on id, together with one or more occurrences of the -x
parameter. Example:

```
amo upload lightning \
    -x linux lightning-linux.xpi \
    -x mac lightning-mac.xpi \
    -x win lightning-win32
```

### Editor commands
These commands are meant for AMO editors. They will fail in random ways if you
are not.

#### amo list
Show information from the editor queue. The queue name can be the last part of
the url, or a slightly shortened variant:
* Unlisted: `unlisted/nominated`, ` unlisted/pending`
* Listed: `new`, `updates`,

### amo logs
Show review log information. The log list name is again the last part of the
url, but currently only the add-on review log is supported (reviewlog).

The logs may be queried by date with the `-s` and `-e` parameters, the dates
are inclusive and in the local timezone (while addons.mozilla.org always uses
Pacific time). Also, you can query by add-on, editor or comment with the `-q`
parameter.

### amo get
Downloads one or more versions to the hard drive for review. Will download both
the xpi and the sources and once done extract each package. The files will be
saved in a sub-directory named after the addon id in the current (or specified)
directory.

When specifying version numbers you can also use the tag `latest` to retrieve
the latest version and the `previous` tag to get the last accepted version.
This is useful when specifying multiple versions to download.

A commonly used option is the diff option `-d`, which automatically gets the
latest and previous versions. This is useful to compare versions.

Example:

```
amo get -d lightning
```

### amo info
Shows information about an add-on, including versions, reviews and file states.

### amo decide
Decides on an add-on review. If the message argument is omitted, an editor is
opened to write the message. If you pass `-` as the addon argument, add-on ids
will be read through stdin.

Example:

```
amo decide -a reject lightning
```
