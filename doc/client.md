Client
======



Overview
--------

Basically, the update client does two things:
- query the update server for available updates
- apply the eventual update (i.e. download and write the data)

To query the server, the client sends a request in the form of:
`<release>/<product>/<arch>/<variant>/<branch>/<version>/<buildid>.json`

If the server replies with an HTTP 404 error, the client will retry
with the generic fallback request `<release>/<product>/<arch>/<variant>/<branch>.json`
or `<release>/<product>/<arch>/<variant>/<branch>.cpN.json` in case the current
image is past the checkpoint N.

The server replies with a JSON that describes the available updates (there might be
more than one). If no updates are available, it replies with an empty JSON object,
i.e. `{}`.

Applying the update, then, boils down to invoking rauc with the given url.

Implementation-wise, the two steps described above (query for update and apply
an update) are really separated, so that the client can do:
- step 1: the client queries the server, receive an answer (a JSON file), save
  it somewhere and bail out. This can be performed using the `--query-only`
  argument.
- step 2: the client open an existing JSON file describing an update, and apply
  it. To use an existing JSON file the argument `--update-file` needs to be
  provided
- step 1 + step 2: the client query for update, get an answer, then apply it.
  This is currently the default behavior.


The client configuration file
-----------------------------

The client, in order to run, requires a configuration file.
The structure is similar to the Windows INI files, consisting of different
sections, each of which contains keys with values.

#### Mandatory sections and keys

The only mandatory section is `Server`, and it must contain at least the
following keys:

- `MetaUrl`: The base URL used to query for updates
- `ImagesUrl`: The base URL used to download image updates
- `Variants`: List of known variants, separated by a semicolon
- `Branches`: List of know branches, separated by a semicolon

#### Optional sections and keys

A configuration file might also have the `Host` section with the key `RuntimeDir`.

`RuntimeDir` is used to specify the path to the directory where the downloaded JSON file will be
stored.

[image manifest]: overview.md#the-image-manifest


Query request details
---------------------

To query the update server an HTTP `GET` request is sent.

For example a request will look like this:
`https://steamdeck-atomupd.steamos.cloud/meta/holo/steamos/amd64/steamdeck/stable/3.6.0/20240124.1.json`

The base server URL is taken from the `MetaUrl` field in the
[configuration file][].

All the values that follows identify the image that the client is currently using.
Those values are taken from the [image manifest][].

The only exception are the variant and branch, which can be used to request different images,
respectively to jump to a different variant or ask for a different branch.

[configuration file]: #the-client-configuration-file


Update request details
----------------------

To download the actual update an HTTP `GET` request is sent.

For example a request will look like this:
`https://steamdeck-images.steamos.cloud/steamdeck/20240104.1/steamdeck-20240104.1-3.5.13.raucb`

The URL is composed by two parts:

- The base server URL, taken from the `ImagesUrl` field in the
  [configuration file][].
- The path to the file that needs to be downloaded, taken from the
  `update_path` field in the [JSON that the server provided][] after our initial
  query.

The RAUC bundle file is directly installed by using `rauc install URL`.
In order for this to work, the client is expecting the server to provide the
casync chunk store in the same URL location (with the `.castr` extension
instead of `.raucb`).
So in the example used before, the client expects the casync chunk store to be
located in:
`https://steamdeck-images.steamos.cloud/steamdeck/20240104.1/steamdeck-20240104.1-3.5.13.castr`


[JSON that the server provided]: server.md#structure-of-update-candidates

Update scenarios
----------------

#### Scenario 1 - Unattended

This is the case of a Steam device that will boot in "low-power mode", sneakily
during the night, and update itself without asking for permission.

In this case, we just need a systemd service file that invokes the client after
the boot is complete. The client does all the job of querying for an update,
and applying it if it's found, then exit. After it exits, systemd should either
poweroff or reboot the device.

Note that we WANT to reboot (and not poweroff) after an update is applied. And
the machine should boot with full capabilities (not low-power), so that the GPU
is enabled, and things like building the graphics driver (i.e. dkms) can happen.
Only after this is done, we can consider that the update is complete, which
means that the user can boot his device and use it immediately, rather than
wait 2 minutes because dkms is running to "finish" the update (that would be
poor user experience).

Additionally, only after the device was successfully booted with full
capabilities (by opposition to the low-power mode) we can consider that this
image is valid, and mark it as such. Only then we can keep going and update
again, in case there was more than on update to apply

Implementation-wise: the systemd service must know if an update was applied
(and therefore reboot the device) or not (and therefore simply power it off).
This can be achieved simply if the client return a meaningful exit code, e.g.
`0` if no update was applied, and `1` if an update was applied.

#### Scenario 2 - Attended

This is the case where SteamOS is installed on some custom hardware, for
example a laptop, or on battery powered handheld devices, for example the
Steam Deck. The "low-power mode" is either not available or doesn't make sense
to be used, so updates have to run at some point when SteamOS is up. It also
means that there's a user around, and  we can take this chance to ask him
questions.

In this case, we expect to run the client in `query-only` mode on a regular
basis. In query-mode, the client only queries the server, and if an update is
available, it just drops a JSON file that describes this update in the
directory specified by the configuration key `RuntimeDir` or, as a fallback, to
`/run/steamos-atomupd`. It doesn't apply the update.

So we can run the client in query mode every hour or so. Additionally, we can
have a UI that is notified when an update file is created, and can then notify
the user that a new version is available. The user could then decide to update
now. Or could also do nothing. On shutdown, we could also prompt the user again
and propose to update.

Note that the update in itself (i.e. casync):
- is CPU intensive, so we can't really run it in the background
- downloading and applying the update are mixed together, so we can't download
  data in the background, and then "only" write it to disk when the user says
  ok.

So I don't think we can get away with any kind of transparent or lightweight
update. As long as we use casync, nothing can be prepared in advance, and when
the user agrees to update, everything must be done now, meaning it takes time.



The bits of logic client-side
-----------------------------

As said before, most of the logic is server-side. However, the server might
return more than one update candidates, so the client must be able to handle
that, and choose among a list of possible update candidates which one to apply.

**A list of updates**

In case there's some checkpoint updates ahead, then the server might return an
update path with more than one update, even though the client can install only
one at a time. Why does the server returns a list then? Because it's useful to
know how many updates are needed for the client to be up-to-date. For example:

- Running *attended*: if there's a living user on the other side, then it's
  nice to be able to tell him that there's 3 updates to apply, and that we
  will need to reboot three times, don't worry it's normal, be patient.
- Running *unattended*: I'm not sure that it's useful for this use-case, as
  the device has to restart anyway after an update, and then it can probably
  check if another update is available at this moment.

**Distinction between minor and major**

For legacy reasons the client receives the update candidates in a JSON object
called `minor`. Initially the update system was designed to support both
`minor` and `major` upgrades. However, this distinction has been deprecated.

Now all updates are `minor` updates. Bigger updates that brings breaking changes
should instead introduce a checkpoint, to mark the point of no return.
