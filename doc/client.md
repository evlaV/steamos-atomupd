Client
======



Overview
--------

Basically, the update client does two things:
- query the update server for available updates
- then, apply the update (i.e. download and write the data)

To query the server, the clients sends a request with a few arguments to
introduce himself and say what image he's running. The arguments are taken from
the manifest file, basically: *product*, *release*, *variant*, *arch*,
*buildid* and *version*. Additionally, in theory the client could say that it
wants to receive unstable updates, even if currently the only way to achieve
that is by setting *version* to the special value `snapshot`, effectively
preventing the client to ask for versioned unstable updates.

The server looks among the images that are available, and then decides if
there's an update path for the client or not. If so, it answers some JSON
data describing the available updates (there might be more than one). If no
updates are available, it replies with an empty JSON object (i.e. `{}`) or if
the request is malformed (e.g. missing an expected argument) it replies with an
HTTP 400 response status code.

Among the possible updates offered by the server, the client should be able
to decide which one to apply by itself (especially if it runs unattended), or
prompt the user if needed (for example, in case a major update is available).

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
keys `QueryUrl` and `ImagesUrl`.

When the client asks for updates it will use the URL specified in `QueryUrl`.
Instead, when the actual image update needs to be downloaded, it will use the
URL in `ImagesUrl`.

Check [Query request details][] and [Update request details][] for more info.

[Query request details]: #query-request-details
[Update request details]: #update-request-details

#### Optional sections and keys

A configuration file might also have the `Host` section with the keys
`Manifest` and/or `RuntimeDir`.

`Manifest` is used to specify the path to the [image manifest][] and
`RuntimeDir` the path to the directory where the downloaded JSON file will be
stored.

[image manifest]: overview.md#the-image-manifest


Query request details
---------------------

To query the update server an HTTP `GET` request is sent.

For example a request will look like this:
`https://example.com/update?product=steamos&release=holo&variant=jupiter&arch=amd64&version=snapshot&buildid=20211022.4&checkpoint=False`

To the base server URL, taken from the `QueryUrl` field in the
[configuration file][], is appended a question mark followed by multiple "query"
parameters, in the form of "key=value", separated by an ampersand (following
the [RFC 3986][] specification).

`product`, `release`, `variant`, `arch`, `version`, `buildid` and `checkpoint`
are all guaranteed to be present as "query" parameters.
Their values are taken from the [image manifest][].

However, if the `manifest.json` has an empty value for one of these parameters,
e.g. `"product": ""`, the client will not throw any error while parsing that
JSON, and the resulting `GET` request will have `[...]?product=&release=[...]`.

Additionally `checkpoint` is expected to be a boolean, so the GET request
usually terminates with either `&checkpoint=False` or `&checkpoint=True`.
If `checkpoint` is missing from the manifest file, by default its value will
be assumed to be `False`.
However, while parsing the `manifest.json` file, its type is not enforced.
For this reason if the JSON had some unexpected value like
`"checkpoint": "maybe"`, the request will contain `[...]&checkpoint=maybe`.

[configuration file]: #the-client-configuration-file
[RFC 3986]: https://datatracker.ietf.org/doc/html/rfc3986#section-3


Update request details
----------------------

To download the actual update an HTTP `GET` request is sent.

For example a request will look like this:
`https://example.com/jupiter/20211022.4/jupiter-20211022.4-snapshot.raucb`

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
`https://example.com/jupiter/20211022.4/jupiter-20211022.4-snapshot.castr`


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

The server separates updates in two: the `minor` updates (i.e. updates within
the same release) and the `major` updates (i.e. updates to the next release).

Why? Because if we know that there's a user at the other end, we might want to
ask him before doing a major update of his device. Major updates take time and
can break things, so doing so without warning is not super nice.

This way, we can have a GUI showing up client-side, telling the client that
a major update is available, and does he want to install it or not?
