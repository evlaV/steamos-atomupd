Tests to do
-----------

#### Server

Ensure releases are sorted in the config file


#### Client

Check how things behave when there's no network

Config file
- a config file MUST exist
- some keys in config file are mandatory

Server expectations:
- if no update is available, the server should return an empty response

When running with 'query-only':
- if an update is avail, then an update file should be downloaded in runtime dir
- if no update is avail, then any update file should be removed from runtime dir

When parsing update file received from the server:
- be able to select one release amongs those proposed by the server:
  - 1st: lower checkpoint from next
  - 2nd: lower checkpoint from current
  - 3rd: latest from next
  - 4th: latest from current
- handle missing fields (because all fields are optional)
