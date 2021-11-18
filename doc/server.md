Server
======



Overview
--------

The server requires a configuration file with a bunch of mandatory params:
- the directory where images live
- whether images are snapshots or not
- the list of supported products (eg. `steamos`)
- the list of supported releases (eg. `clockwerk`)
- the list of supported variants (eg. `atomic`)
- the list of supported architectures (eg. `amd64`)

An update server is stateless, and several update servers can run on the same
machine, serving different sets of images, possibly all of them living in the
same directory.

On start, the server walks the image directory, looking for **manifest files**.
Each image should have a manifest file, with the extension `.manifest.json`.
These files are parsed, and the server decides if the image is counted in, or
discarded (based on product, release, arch, variant, etc...).

The server does not care about how images are organized (ie. a hierarchy like
`/steamos/clockwerk/3.1/amd64`) or named (ie. `steamos-3.0-amd64-atomic.img`).
However, the server expects that all the build artifacts for an image have the
same filename, and only the extension should differ. More precisely, there
should be a RAUC bundle with the extension `.raucb`, and a CASync store with
the extensions `.castr`.

The server is configured to work either with **snapshot images**, either with
**versioned images**. Both kind of images can't be mixed. If the server is
configured for snapshot images, it will discard every versioned images it
finds in the image directory, and it will reply nothing to clients that come
with a versioned image. If the server is configured for versioned images, the
opposite happens: snapshots are discarded, and clients that run a snapshot
won't be proposed an update.

Internally, versioned images are compared according to their versions, which
follows semantic versioning. Snapshot images, for which the version is null,
are compared according to their release and build ids.

The server is **release aware**, ie. it makes an assumption that releases are
strings, and they grow alphabetically, so they can be compared. It means that
`brewmaster < clockwerk < doom` (note that cycling from `z...` to `a...` is not
implemented). This is needed in order to compare build ids (which are dates).



Version selection
-----------------

When a client shows up and asks the server about available updates, it says
what image it's running. It gives all the  details that are in the manifest
file: which *product* it's running, on which *arch*, and the current *release*,
*variant*, *version* and *buildid*. In a first pass, the server selects all the
images for this (product,release,variant,arch) tuple that are newer: these are
all update candidates.

However, among all these candidates, not all of them are relevant. The server
must refine this list, and only provide to the client updates **that must be
applied in order to be up-to-date**. Intermediary updates that are not needed
must not be part of the answer.

For example, if the client runs `3.0`, and the versions `3.1`, `3.2` and `3.3`
are available, then the server should only answer with the `3.3` version, as
there's no point upgrading to intermediary versions.

Unless some of these versions are checkpoints: in the example above, if `3.1`
is a checkpoint, then the answer will answer with `3.1` and `3.3`, so that the
client knows that it has two updates to apply in order to be up-to-date.

Additionally, the client can theoretically say whether it's interested in
unstable updates, in such case the server considers images such as `3.4-rc1`
(versions strings are expected to follow semantic versioning). However there
isn't yet a proper way for the client to signal its interest in unstable
updates.

Additionally, there could be a new *release* available. In this case, the
server will return a second list of relevant updates, for the next release.

In the end, the answer from a server could be something like this:

    minor: 3.1(C), 3.4
    major: 4.2

#### Additional thoughts

As a rule of thumb, most logic should be server-side, and the client should
be as dumb as possible. Because we can modify the server anytime, while we
have to live with the clients deployed out there in the wild, for an
undefined period of time.

So we try to decide as much things as we can server-side, however there are
things we can't always decide. For example, the decision to apply or not a
major update could be left to the user (in case the update is attended, and
there's an user that can confirm if he wants to apply a major update).

That's why we provide two update paths, minor and major: to allow the client
to make a decision in this particular case.



Knowing details about the client
--------------------------------

As said above, we try to make decisions server-side, as much as possible. The
server can make an informed decision only if it knows enough about the client.

For that purpose, the client gives the details of the image it's running,
according to the manifest file installed in `/usr`. Additionally, it says
whether it wants unstable images.

However, I believe this might not be enough, especially for major updates. What
if we want to ship a new release, however it's been tested only with device A,
but it's not yet ready for device B? In this case, we must know if the client
is running on device A or device B, in order to propose a major update or not.

So I think it would be useful if the client can provide some basic hardware
details as well, at least to identify the SteamOS devices we support.

For users running SteamOS on their own hardware, maybe we could at least
provide details about the graphics hardware in the request? As it's probably
the most relevant information, and we might know that a particular, new release
ships with a new version of the NVidia drivers, and that this version dropped
support for this particular GPU.

**This is still an open question and needs to be discussed**



The image pool
--------------

Here's how images can be sorted in the image pool (this is not a requirement,
just an example):

    images
    ├── snapshots
    │   └── steamos
    │       ├── clockwerk
    │       │   ├── 20181105.1
    │       │   │   └── amd64
    │       │   │       └── steamos-clockwerk-20181105.1-snapshot-amd64-atomic.manifest.json
    │       │   └── 20181108.1
    │       │       └── amd64
    │       │           ├── steamos-clockwerk-20181108.1-snapshot-amd64-devel.manifest.json
    │       │           └── steamos-clockwerk-20181108.1-snapshot-amd64-atomic.manifest.json
    │       └── doom
    │           └── 20181105.1
    │               └── amd64
    │                   └── steamos-clockwerk-20181105.1-snapshot-amd64-atomic.manifest.json
    └── releases
        └── steamos
            └── clockwerk
                └── 3.0
                    └── amd64
                        └── steamos-clockwerk-20181110.0-3.0-amd64-atomic.manifest.json

This is quite verbose, but as you can see:

- The image name carries most of the information from the manifest file, which
  is convenients for developers who download a bunch of images in the same
  directory.
- the directory hierarchy also reflects the image manifest. For snapshot images
  we store the image per build id (ie. `20181105.1`), while for released images
  we use the version (ie. `3.0`). This allows to have things neatly sorted.

Storing the buildid (ie. the date) in the image name (or as part of the
directory hierarchy) has its pros and cons.

The pros:
- We're sure we don't risk overwritting anything, for any reason, as the
  buildid is supposed to be unique.
- Knowing when an image was built is always useful.
- Downloaded images are naturally sorted by date.

The cons:
- The url of a released image is not predictable anymore. So if you want to
  write a dev tool that automatically fetches the image version `3.0` or
  `latest` image, it's not straightforward, because you can't get the URL out of
  the version.



Infrastructure considerations
-----------------------------

The way it works, the update server needs to access an image pool, which means
that it must live on the same machine as the images. It seems to be a
reasonable pre-requisite.

Also, even though it's not been discussed, (and maybe it's not much relevant
here), I assume that we'll have two infrastructures:
- one public: with production and beta images.
- one private: with production, beta, alpha, snapshots and more.

We could consider that the public infra is just a subset of the private infra,
and that promoting some images from the private to the public infra will boil
down to just copying an image from a private to a public machine.
