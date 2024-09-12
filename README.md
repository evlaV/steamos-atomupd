SteamOS Atomic Update
=====================

This is the atomic updater for SteamOS. Read `doc/*` for details.



Build
-----

Get your build depends please:

    apt install debhelper meson

Build and test with meson / ninja:

    meson setup build
    meson compile -C build // or ninja -C build (meson 0.53 and older)
    meson test -C build


Run
---

Install runtime dependencies:

    apt install python3-flask python3-semantic-version

Run locally:

    # Create the images hierarchy. If you want mock images you can look at
    # `tests/createmanifests.py`

    # Create the meta JSON files
    export IN_SOURCE_TREE=1
    ./bin/steamos-atomupd-staticserver --debug --config examples/server-releases.conf


Integration
-----------

#### Client-side

Install the client:

    apt install steamos-atomupd-client

Create a configuration file at `/etc/steamos-atomupd/client.conf`:

    mkdir -p /etc/steamos-atomupd
    vi /etc/steamos-atomupd/client.conf
    ----
    [Server]
    MetaUrl = http://localhost:5000
    ImagesUrl = http://localhost:8000

Test the communication with the server:

    steamos-atomupd-client --query-only

#### Server-side

One way to let the meta server automatically notice changes to the images pool is to create
a systemd path unit, for example:
```ini
[Unit]
Description=Atomic-update image monitoring

[Path]
PathChanged=/[...]/steamdeck/updated.txt
```

With a corresponding `.service` that executes the static server.

Finally, when you want to refresh the meta JSON files, you can just touch the `updated.txt`
file.


Improvements and TODOs
----------------------

Grep for TODO in the code.

See tests/TODO.md

**Both**

I think the `manifest.json` file was a mistake: I think the [os-release][] file
fits the bill already. So I'd prefer to just drop the manifest file, and use an
`os-release` file instead.

[os-release]: https://www.freedesktop.org/software/systemd/man/os-release.html

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

Check how the client behave when there's no network, possibly add some test
cases?

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

Also, for dev it would be nice to have a special "list" request, and the server
would return the full list of images.

When the client exists (throught Ctrl-C for example), we should make sure that
all the subprocess (ie. rauc) are terminated as well. I don't think it's the
case at the moment.

**Hardening**

We should go over the TUF things, and implements some security improvements
that make sense. I think it's mostly client-side things. See
<https://theupdateframework.github.io/>.

In the client, we could enforce https and refuse http, maybe with an explicit
configuration setting to allow http if need be. The idea is mostly to prevent
configuration mistakes, because in production you probably don't want to start
your update from an untrusted source.

