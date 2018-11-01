SteamOS Updater
===============

Run locally:

    export IN_SOURCE_TREE=1
    ./bin/steamos-update-client

Build a package:

    gbp buildpackage \
        --git-force-create \
        --git-upstream-tree=HEAD
