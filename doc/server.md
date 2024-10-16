Server
======



Overview
--------

The server requires a configuration file with a bunch of mandatory params:
- the directory where images live
- whether images are snapshots or not
- the list of supported products (e.g. `steamos`)
- the list of supported releases (e.g. `holo`)
- the list of supported variants (e.g. `steamdeck`)
- the list of supported branches (e.g. `stable`)
- the list of supported architectures (e.g. `amd64`)

An update server is stateless, and several update servers can run on the same
machine, serving different sets of images, possibly all of them living in the
same directory.

On start, the server walks the image directory, looking for **manifest files**.
Each image should have a manifest file, with the extension `.manifest.json`.
These files are parsed, and the server decides if the image is counted in, or
discarded (based on product, release, arch, variant, etc...).

The server does not care about how images are organized (e.g. a hierarchy like
`/steamos/holo/3.1/amd64`) or named (e.g. `steamos-3.0-amd64-steamdeck.img`).
However, the server expects that all the build artifacts for an image have the
same filename, and only the extension should differ. More precisely, there
should be a RAUC bundle with the extension `.raucb`, and a CASync store with
the extensions `.castr`.

The server is able to mix and match snapshots and versioned images.

Internally, versioned images are compared according to their versions, which
follow semantic versioning, and the buildid. Snapshot images, for which the
version is null, are compared only with their buildid.


Update selection
-----------------

A typical update request from a client is in the form of:
`<release>/<product>/<arch>/<variant>/<branch>/<version>/<buildid>.json`

*release*, *product*, *arch*, *version* and *buildid* are all values that
identify the image that the client is currently using. Those values are taken
from the manifest file.

Instead, *variant* and *branch* can be used to request different images, respectively
to jump to a different variant or ask for a different branch.

The server also provides generic fallback responses, useful when the client is running
an unknown version and buildid, e.g. an old image that was removed from the server
without using the `skip: True` option.
The generic fallback response is in the form of:
`<release>/<product>/<arch>/<variant>/<branch>.json`
If the client is past a checkpoint N, the JSON file that will be requested is going
to be `<branch>.cpN.json` instead.

One exception is for old legacy images prior to the introduction of branches.
For them, the update request is in the form of:
`<product>/<arch>/<version>/<variant>/<buildid>.json`

Among all the matching possible image updates, the server only proposes the latest
one. It skips all the intermediary updates, unless there are checkpoints involved.

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

Additional remote config info
-----------------------------

Clients have a hardcoded list of known branches and variants that the server is
supposed to provide. However, those lists can also be updated using the `remote-info.conf`
file on the server side.

That file is stored in `<release>/<product>/<arch>/<variant>/remote-info.conf` and has
the following structure:
```ini
[Server]
Variants = steamdeck
Branches = stable;rc;beta;bc;preview;pc;main
```

To let the server automatically generate this file, you can use the option
`GenerateRemoteInfoConfig` in the server configuration file.

Structure of update candidates
------------------------------

When the server is queried about an update, it will reply to the client with
a JSON object containing information about the available updates.
Otherwise, if there are no updates, it will reply with an empty JSON object
(i.e. `{}`).

When an update is available, the JSON *object* has the following keys:
```
**minor**
:   An object describing minor system updates.
    If there are no minor update, this object will be omitted.
    The keys are strings:

    **release**
    :   A short string identifying the operating system release codename,
        for example **buster** for Debian 10 'buster' or **holo** for
        SteamOS 3. This is usually the **VERSION_CODENAME** from
        **os-release**(5).

    **candidates**
    :   An array of objects, each of them describing a possible update.
        Every object has the following keys:

        **update_path**
        :   Relative path pointing to the rauc bundle file, needed to
            initialize the update. For example
            `jupiter/20211022.4/jupiter-20211022.4-snapshot.raucb`

        **image**
        :   An object with the details of the proposed image update.
            The keys are strings:

            **product**
            :   A short string identifying the operating system, for example
                **arch** or **steamos**. This is usually the **ID** from
                **os-release**(5).

            **release**
            :   The same **release** explained before

            **variant**
            :   A short machine-readable string identifying the flavor/type
                of the operating system, for example **steamdeck**.
                This is usually the **VARIANT_ID** from **os-release**(5).

            **branch**
            :   A short machine-readable string identifying in which branch
                the operating system is at, for example **stable**.

            **default_update_branch**
            :   A short machine-readable string identifying which branch this image
                will default to, unless the users explicitly selects a branch,
                for example **stable**.

            **arch**
            :   A string identifying the image architecture, for example
                **amd64** or **i386**.

            **version**
            :   A string that is either a semantic version (https://semver.org),
                or the special keyword `snapshot`.

            **buildid**
            :   A string in the `ISO-8601 date` basic format, followed by an
                optional `.` and a number called the `build increment`.

            **estimated_size**
            :   An integer representing the estimated download size, in Bytes,
                to perform the update. When this key is either missing, or its
                value is zero, the estimated size should be assumed to be
                unknown.

            **requires_checkpoint**
            :   An integer indicating which checkpoint the client must be past
                in order to install this image. If missing, it implicitly means
                that the image doesn't require to be past any checkpoint.

            **introduces_checkpoint**
            :   An integer that, if greater than zero, indicates that this image
                is a checkpoint. If missing, it implicitly means that this
                image is not a checkpoint.

            **shadow_checkpoint**
            :   A boolean value indicating whether this image is a shadow
                checkpoint or not.

**major**
:   An object describing major system updates.
    If there are no minor update, this object will be omitted.
    The keys are the same as **minor**.
```

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


How to retire a broken/undesired image
--------------------------------------

To remove an image from the update candidates pool you should set the **skip**
option, in its manifest, to `true`. E.g.:
```
{
  "product": "steamos",
  "release": "holo",
  "variant": "steamdeck-main",
  "arch": "amd64",
  "version": "snapshot",
  "buildid": "20221202.1000",
  "checkpoint": false,
  "estimated_size": 0,
  "skip": true
}
```

With this option, the server will not use the image as an update candidate.
Additionally, all clients that were using this image, will be prompted to
either upgrade, whether possible, or downgrade.

When adding the **skip** option it is also possible, if desired, to remove
both the associated RAUC bundle file and the Casync/Desync chunks.

NOTE: Please keep in mind that unless you really know what you are doing, you
should NOT delete the image manifest, or alter its other properties.
This could leave the static server in an unexpected state.
