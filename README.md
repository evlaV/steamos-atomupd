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
    ./bin/steamos-update-client -d -c examples/client.conf --query-only



Integration
-----------

#### Client-side

Install the client:

    apt install steamos-update-client

Create a configuration file at `/etc/steamos-update/client.conf`:

    mkdir -p /etc/steamos-update
    vi /etc/steamos-update/client.conf
    ----
    [Server]
    QueryUrl = http://localhost:5000
    ImagesUrl = http://localhost:8000
   
Test the communication with the server:

    steamos-update-client --query-only

#### Server-side

Install the server:

    apt install steamos-update-server

Create a configuration file in `/etc/steamos-update/server`:

    mkdir -p /etc/steamos-update/server
    vi /etc/steamos-update/server/snapshots.conf
    ----
    # see `examples/server-snapshots.conf`

Start the server:

    systemctl start steamos-update-server@snapshots.service

If it all works, don't forget to enable the service:

    systemctl enable steamos-update-server@snapshots.service



Server Overview
---------------

The server requires a configuration file with a bunch of mandatory params:
- the directory where images live
- whether images are snapshots or not
- the list of supported products (eg. `steamos`)
- the list of supported releases (eg. `clockwerk`)
- the list of supported variants (eg. `rauc`)
- the list of supported architectures (eg. `amd64`)

On start, the server walks the image directory, looking for **manifest files**.
Each image should have a manifest file, with the extension `.manifest.json`.
These files are parsed, and the server decides if the image is counted in, or
discarded (based on product, release, arch, variant, etc...).

The server does not care about how images are organized (ie. a hierarchy like
`/steamos/clockwerk/3.1/amd64`) or named (ie. `steamos-3.0-amd64-rauc.img`).
However, the server expects that all the build artifacts for an image have the
same filename, and only the extension should differ. More precisely, there
should be a RAUC bundle with the extension `.raucb`, and a CASync store with
the extensions `.castr`.

The server is configured to work either with **snapshot images**, either with
**versioned images**. Both kind of images can't be mixed. If the server is
configured for snapshot images, it will discard every versioned images it
finds in the image directory, and it will reply nothing to clients that come
with a versioned image.

Internally, versioned images are compared according to their versions, which
follows semantic versioning. Snapshot images, for which the version is null,
are compared according to their release and build id.

The server is **release aware**, ie. it makes an assumption that releases are
strings, and they grow alphabetically, so they can be compared. It means that
`brewmaster < clockwerk < doom`. Note that cycling from `z...` to `a...` is not
implemented.



Manifest Overview
-----------------

An *image manifest* describes an image. It's a JSON file.

**Mandatory fields**

- product: `steamos`
- release: `brewmaster`, `clockwerk`
- variant: `devel`, `rauc`
- arch: `amd64`
- version: `3.0`, `snapshot`
- buildid: `20190214.1`

The version must be a [semantic version](https://semver.org/), or must be the
special keyword `snapshot` for a snapshot.

The buildid must be an *ISO-8601 date* in the basic format, followed by an
optional `.` and a number called the *build increment*.

**Optional fields**

- checkpoint: `true` or `false`

