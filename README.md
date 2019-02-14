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



Overview
--------

#### Manifest

An *image manifest* describes an image. It's a JSON file.

**Mandatory fields:**
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

**Optional fields:**
- checkpoint: `true` or `false`

#### Server

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



Improvements and todos
----------------------

Grep for TODO in the code.

**Server**

The server doesn't watch the images directory, so when a new image is added, the
server has to be restarted manually. We could improve that by adding a watch of
some sort, to be notified when some new files are added. Beware though that a
casync store can have up to 100k files and directories, it makes things tricky.

On startup, the server walks the images directory. If it contains a casync
store, then we have to walk all the 100k files and directories. Multiply that
by the number of casync stores, and you understand now why the server can be a
bit slow to start.

**Client**

In the client request, we should add a bit more details. What comes to mind at
the moment:
- basic information about the client hardware. So that if we're notified that
  some update breaks hardware X, we can turn a switch server-side, and stop
  serving this update to hardware X. Another application is to be able to
  deploy a major update for only supported steamos devices, letting the old
  generation live with old version. I'm not sure exactly what details would
  be useful, and if there's some privacy concerns, so we want to discuss that.
- maybe say if we're running attended or unattended, somehow? I'm not certain
  it would be useful though.

**Hardening**

We should go over the TUF things, and implements some security improvements
that make sense. I think it's mostly client-side things. See
<https://theupdateframework.github.io/>.

In the client, we could enforce https and refuse http, maybe with an explicit
configuration setting to allow http if need be. The idea is mostly to prevent
configuration mistakes, because in production you probably don't want to start
your update from an untrusted source.

**Testing**

We have a few unit tests, now the next would be to have more advanced tests in
different scenarios, to ensure that both server and client behave as expected.
Am I talking about acceptance tests? Here come a few ideas of things to test:
- test that the 'want-unstable' flag is honored by the server, and works as
  expected on the client-side as well (getting a boolean from a config object
  is error-prone).
- ensure that both client and server behave when there's no update available.
- ensure that if no update is available, there's no update file in the runtime
  dir (ie. even if there was a file before the client runs, the file should be
  deleted).
- ensure that the client returns 0 when no update is performed, and 1 if an
  update is performed.
