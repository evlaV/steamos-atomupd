Overview
========



The image manifest
------------------

An *image manifest* describes an image. It's a JSON file, and it's created
during an image build, along other build artifacts. An image manifest is
installed within the image in `/usr`, and it's also part of the build
artifacts.

#### Mandatory fields

- product: `steamos`
- release: `brewmaster`, `clockwerk`
- variant: `devel`, `rauc`
- arch: `amd64`
- version: `3.0`, `snapshot`
- buildid: `20190214.1`

The **version** must be a [semantic version](https://semver.org/), or must be
the special keyword `snapshot` for a snapshot.

The **buildid** must be an *ISO-8601 date* in the basic format, followed by an
optional `.` and a number called the *build increment*.

#### Optional fields

- checkpoint: `true` or `false`



Checkpoints
-----------

Checkpoints are releases that can't be avoided. To give an example:

    A - B - ₡ - D - E - ...

C is flagged as a checkpoint. Any upgrade the traverses C must be split into
two: The user must boot C at least once on the way.

This will allow us to manage transitions by having a C that performs any
complex steps or involved package-wrangling required for difficult upgrades,
and means we can manage such operations in the OS itself, instead of adding
complexity to the upgrade system itself.

We might want to handle upgrades from one release to another in a similar way,
although those wouldn't strictly be checkpoints since you could jump from an
ongoing clockwerk series to an ongoing doom series - probably in that case you
are required to jump to doom@0 which would be a special revision that handled
any special requirements for a clockwerk-doom transition.

So going from clockwerk-earthshaker would involve:

    clockwerk@current → doom@0 → earthshaker@0 → earthshaker@current



Client and server
-----------------

Please look at `client.md` and `server.md` for details.
