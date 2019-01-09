SteamOS Updater
===============


Build
-----

Get your build depends please:

    apt install debhelper meson

Build the package with gbp:

    gbp buildpackage \
        --git-force-create \
        --git-upstream-tree=HEAD



Run
---

Install runtimes depends:

    apt install python3-flask python3-semantic-version

Run locally:

    # Create a fake image hierarchy
    ./examples/build-image-hierarchy.sh

    # DON'T FORGET THAT STEP!
    export IN_SOURCE_TREE=1

    # Shell #1
    ./bin/steamos-update-server -d -c examples/server-daily.conf

    # Shell #2
    ./bin/steamos-update-client -d -c examples/client.conf



Server Overview
---------------

The server requires a configuration file with a bunch of mandatory params:
- the directory where images live
- the versioning scheme expected (`semantic` or `date-based`)
- the list of supported products (eg. `steamos`)
- the list of supported releases (eg. `clockwerk`)
- the list of supported architectures (eg. `amd64`)
- the list of supported variants (eg. `rauc`)

When started, the server walks the image directory, looking for manifest files.
Each image should have a manifest file. These files are parsed, and the server
decides if the image is counted in, or discarded (based on product, release,
arch, variant, etc...).

The server does not care about how images are organized (ie. a hierarchy like
`/steamos/clockwerk/3.1/amd64`) or named (ie. `steamos-3.0-amd64-rauc.img`).
However, the server cares about serving a RAUC bundle, and it expects the RAUC
bundle to have a particular name and location, relative to the manifest file.
This is hard-coded for the moment, out of a better idea to make that more
"generic".

The server is *release aware*, ie. it makes an assumption that releases are
strings, and they grow alphabetically, like this:

    brewmaster = 2.x
    clockwerk = 3.x
    doom = 4.x
    ...

However, cycling from `z...` to `a...` is not implemented.

