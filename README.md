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
Show information from the editor queue. The queue name is the last part of the
url, for example:
* Unlisted: `unlisted_queue/nominated`, ` unlisted_queue/pending`, `unlisted_queue/preliminary`
* Listed: `queue/fast`, `queue/nominated` `queue/pending` `queue/preliminary` `queue/reviews`

```
usage: amo [-h] [-u]
           [-q {unlisted_queue/nominated,unlisted_queue/pending,...}]

optional arguments:
  -h, --help            show this help message and exit
  -u, --url             output add-on urls only
  -q {unlisted_queue/nominated,...}, --queue {unlisted_queue/nominated,...}
                        the queue name or url to list

```

### amo logs
Show review log information. The log list name is again the last part of the
url, for example:
* Add-on Review Log: `reviewlog`
* Moderated Review Log: `logs`
* Signed Beta Files Log: `beta_signed_log`

The logs may be queried by date with the `-s` and `-e` parameters, the dates
are inclusive and in the local timezone (while addons.mozilla.org always uses
Pacific time). Also, you can query by add-on, editor or comment with the `-q`
parameter.

```
usage: amo logs [-h] [-l LIMIT] [-s START] [-e END] [-q QUERY]
           [-k {date,addonname,version,reviewer,action}] [-u]
           [{reviewlog,logs,beta_signed_log}]

positional arguments:
  {reviewlog,logs,beta_signed_log}
                        the type of logs to retrieve

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
Downloads one or more versions to the hard drive for review. Will download both the xpi and the sources and once done extract each package. The files will be saved in a sub-directory named after the addon id in the current (or specified) directory.

```
usage: amo get [-h] [-o OUTDIR] [-l LIMIT] [-v VERSION] addon

positional arguments:
  addon                 the addon id or url to get

optional arguments:
  -h, --help            show this help message and exit
  -o OUTDIR, --outdir OUTDIR
                        output directory for add-ons
  -l LIMIT, --limit LIMIT
                        number of versions to download
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
Decides on an add-on review. If the message argument is omitted, an editor is opened to write the message.

```
usage: amo decide [-h] [-m MESSAGE]
           addon {info,comment,reject,prelim,super,public}

positional arguments:
  addon                 the addon id or url to decide about
  {info,comment,reject,prelim,super,public}
                        the action to execute

optional arguments:
  -h, --help            show this help message and exit
  -m MESSAGE, --message MESSAGE
                        comment add to the review
```

