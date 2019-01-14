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

Install runtime dependencies:

    apt install python3-flask python3-semantic-version

Run locally:

    # Create a fake image hierarchy
    ./examples/build-image-hierarchy.sh

    # Shell #1
    export IN_SOURCE_TREE=1
    ./bin/steamos-update-server -d -c examples/server-snapshots.conf

    # Shell #2
    export IN_SOURCE_TREE=1
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
Each image should have a manifest file, with the extension `.manifest.json`.
These files are parsed, and the server decides if the image is counted in, or
discarded (based on product, release, arch, variant, etc...).

The server does not care about how images are organized (ie. a hierarchy like
`/steamos/clockwerk/3.1/amd64`) or named (ie. `steamos-3.0-amd64-rauc.img`).
However, the server expects that all the build artifacts for an image have the
same filename, and only the extension should differ. More precisely, there
should be a RAUC bundle with the extension `.raucb`, and a CASync store with
the extensions `.castr`.

The server is *release aware*, ie. it makes an assumption that releases are
strings, and they grow alphabetically, like this:

    brewmaster = 2.x
    clockwerk = 3.x
    doom = 4.x
    ...

Note that cycling from `z...` to `a...` is not implemented.

