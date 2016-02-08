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
           {info,logs,get,list,upload,decide} ...

positional arguments:
  {info,logs,get,list,upload,decide}
  cargs                 arguments for the subcommand

optional arguments:
  -h, --help            show this help message and exit
  -c COOKIES, --cookies COOKIES
                        the file to save the session cookies to
  -d {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --debug {DEBUG,INFO,WARNING,ERROR,CRITICAL}
```

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

Here is the full help text, in case you also need to upload sources:
```
usage: amo upload [-h] [-v] -x {all,linux,mac,win,android} XPI [-b] [-s SOURCE] addon

positional arguments:
  addon                 the addon id to upload

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         show validation messages
  -x {all,linux,mac,win,android} XPI, --xpi {all,linux,mac,win,android} XPI
                        upload an xpi for a platform
  -b, --beta            force uploading this xpi to the beta channel
  -s SOURCE, --source SOURCE
                        add sources to this submission
```

### Editor commands
These commands are meant for AMO editors. They will fail in random ways if you
are not.

#### amo list
Show information from the editor queue. The queue name can be the last part of
the url, or a slightly shortened variant:
* Unlisted: `unlisted/nominated`, ` unlisted/pending`, `unlisted/preliminary`
* Listed: `fast`, `nominated`, `pending`, `preliminary`

```
usage: amo list [-h] [-u]
                [{fast,nominated,pending,preliminary,unlisted/nominated,unlisted/pending,unlisted/preliminary}]

positional arguments:
  {fast,nominated,pending,preliminary,unlisted/nominated,unlisted/pending,unlisted/preliminary}
                        the queue to list

optional arguments:
  -h, --help            show this help message and exit
  -u, --url             output add-on urls only
```

### amo logs
Show review log information. The log list name is again the last part of the
url, but currently only the add-on review log is supported (reviewlog).

The logs may be queried by date with the `-s` and `-e` parameters, the dates
are inclusive and in the local timezone (while addons.mozilla.org always uses
Pacific time). Also, you can query by add-on, editor or comment with the `-q`
parameter.

```
usage: amo logs [-h] [-l LIMIT] [-s START] [-e END] [-q QUERY]
                [-k {date,addonname,version,reviewer,action}] [-u]
                [{reviewlog}]

positional arguments:
  {reviewlog}           the type of logs to retrieve

optional arguments:
  -h, --help            show this help message and exit
  -l LIMIT, --limit LIMIT
                        maximum number of entries to retrieve
  -s START, --start START
                        start time range (in local timezone
  -e END, --end END     end time range (in local timezone, inclusive)
  -q QUERY, --query QUERY
                        filter by add-on, editor or comment
  -k {date,addonname,version,reviewer,action}, --key {date,addonname,version,reviewer,action}
                        sort by the given key
  -u, --url             output add-on urls only

```

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

```
usage: amo get [-h] [-o OUTDIR] [-l LIMIT] [-d] [-v VERSION] addon

positional arguments:
  addon                 the addon id or url to get

optional arguments:
  -h, --help            show this help message and exit
  -o OUTDIR, --outdir OUTDIR
                        output directory for add-ons
  -l LIMIT, --limit LIMIT
                        number of versions to download
  -d, --diff            shortcut for -v previous -v latest
  -v VERSION, --version VERSION
                        pull a specific version
```

### amo info
Shows information about an add-on, including versions, reviews and file states.

```
usage: amo info [-h] addon

positional arguments:
  addon       the addon id or url to show info about

optional arguments:
  -h, --help  show this help message and exit
```

### amo decide
Decides on an add-on review. If the message argument is omitted, an editor is
opened to write the message. If you pass `-` as the addon argument, add-on ids
will be read through stdin.

```
usage: amo decide [-h] [-m MESSAGE] -a
                  {info,comment,reject,prelim,super,public} [-f]
                  [addon [addon ...]]

positional arguments:
  addon                 the addon id(s) or url(s) to decide about

optional arguments:
  -h, --help            show this help message and exit
  -m MESSAGE, --message MESSAGE
                        comment add to the review
  -a {info,comment,reject,prelim,super,public}, --action {info,comment,reject,prelim,super,public}
                        the action to execute
  -f, --force           Do not wait 3 seconds before executing the action
```
