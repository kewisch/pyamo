pyamo - addons.mozilla.org for python
=====================================

These tools provide some classes and a command line tool to access
addons.mozilla.org. This site doesn't have a services API, therefore these
tools use website scraping to determine the right information and use the same
endpoints as they would be used in the browser.


amotool - the command line utility
----------------------------------

General usage as follows, in most cases you don't have to use any of these
options, just the sub-commands:

```
usage: amotool [-h] [-c COOKIES] [-d {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
               {info,list,decide,get} ...

positional arguments:
  {info,list,decide,get}
  cargs                 arguments for the subcommand

optional arguments:
  -h, --help            show this help message and exit
  -c COOKIES, --cookies COOKIES
                        the file to save the session cookies to
  -d {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --debug {DEBUG,INFO,WARNING,ERROR,CRITICAL}
```
### amotool list
Show information from the editor queue. The queue name is the last part of the
url, for example:
* Unlisted: `unlisted_queue/nominated`, ` unlisted_queue/pending`, `unlisted_queue/preliminary`
* Listed: `queue/fast`, `queue/nominated` `queue/pending` `queue/preliminary` `queue/reviews`

```
usage: amotool [-h] [-u]
               [-q {unlisted_queue/nominated,unlisted_queue/pending,...}]

optional arguments:
  -h, --help            show this help message and exit
  -u, --url             output add-on urls only
  -q {unlisted_queue/nominated,...}, --queue {unlisted_queue/nominated,...}
                        the queue name or url to list

```

### amotool get
Downloads one or more versions to the hard drive for review. Will download both the xpi and the sources and once done extract each package. The files will be saved in a sub-directory named after the addon id in the current (or specified) directory.

```
usage: amotool get [-h] [-o OUTDIR] [-l LIMIT] [-v VERSION] addon

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

### amotool info
Shows information about an add-on, including versions, reviews and file states.

```
usage: amotool info [-h] addon

positional arguments:
  addon       the addon id or url to show info about

optional arguments:
  -h, --help  show this help message and exit
```

### amotool decide
Decides on an add-on review. If the message argument is omitted, an editor is opened to write the message.

```
usage: amotool decide [-h] [-m MESSAGE]
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

