Client
======



Overview
--------

Basically, the update client does two things:
- query the update server for available updates
- then, apply the update (ie. download and write the data)

To query the server, the clients sends a request with a few arguments to
introduce himself and say what image he's running. The arguments are taken from
the manifest file, basically: *product*, *release*, *variant*, *arch*,
*buildid* and *version*. Additionally, the client can say that it wants to
receive unstable updates.

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
is enabled, and things like building the graphics driver (ie. dkms) can happen.
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
This can be achieved simply if the client return a meaningful exit code, eg.
`0` if no update was applied, and `1` if an update was applied.

#### Scenario 2 - Attended

This is the case where SteamOS is installed on some custom hardware, for
example a laptop. There's no "low-power mode" here, so updates have to run at
some point when SteamOS is up. It also means that there's an user around, and
we can take this chance to ask him questions.

In this case, we expect to run the client in `query-only` mode on a regular
basis. In query-mode, the client only queries the server, and if an update is
available, it just drops a JSON file that describes this update in a well-known
location. It doesn't apply the update.

So we can run the client in query mode every hour or so. Additionally, we can
have an UI that is notified when a update file is created, and can then notify
the user that a new version is available. The user could then decide to update
now. Or could also do nothing. On shutdown, we could also prompt the user again
and propose to update.

Not that the update in itself (ie. casync):
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

The server separates updates in two: the `minor` updates (ie. updates within
the same release) and the `major` updates (ie. updates to the next release).

Why? Because if we know that there's an user at the other end, we might want to
ask him before doing a major update of his device. Major updates take time and
can break things, so doing so without warning is not super nice.

This way, we can have a GUI showing up client-side, telling the client that
a major update is available, and does he want to install it or not?
