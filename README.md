SteamOS Updater
===============


Build
-----

Build a package:

    gbp buildpackage \
        --git-force-create \
        --git-upstream-tree=HEAD



Run
---

Run locally:

    export IN_SOURCE_TREE=1

    # Shell #1
    ./bin/steamos-update-server -d -c examples/server-daily.conf

    # Shell #2
    ./bin/steamos-update-client -d -c examples/client.conf



TODOs
-----

- Clarify how to handle the image server. Right now it's assumed to be the same
  the one serving update files, but I don't know if we want to support mirrors,
  or if we can always assume that it's the same server for both update file and
  image files.
  Even if it's the same server, we should clarify how to create the image url
  from the server url and the image relative path.



Server Overview
---------------

The server is given two mandatory params:
- the directory where images live
- the versioning scheme expected (`semantic` or `date-based`)

Implementation details: the server finds images by looking for files with a
given extension (`.manifest.json`), parsing this manifest, and looking for
related files (ie. rauc bundle). The server actually does not care about how
images are organized (ie. the directory structure such as
`/steamos/clockwerk/3.1/amd64`), or the way images are named (ie. something like
`steamos-3.0-amd64-rauc.img`). However it cares about serving the rauc bundle,
so it expects the rauc bundle to have a particular name and location, relative
to the manifest file.

#### Release aware

The server is *release aware*, ie. it makes an assumption that releases are
strings, and they grow alphabetically, like this:

    brewmaster = 2.x
	clockwerk = 3.x
	doom = 4.x
	...

However, cycling from `z...` to `a...` is not implemented.
