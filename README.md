SteamOS Update
==============

This is the atomic updater for SteamOS. Read `doc/*` for details.



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

Create a configuration file in `/etc/steamos-update/server/`:

    mkdir -p /etc/steamos-update/server
    vi /etc/steamos-update/server/snapshots.conf
    ----
    # see `examples/server-snapshots.conf`

Start the server:

    systemctl start steamos-update-server@snapshots.service

If it all works, you might want to enable this service persistently:

    systemctl enable steamos-update-server@snapshots.service



Improvements and TODOs
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
