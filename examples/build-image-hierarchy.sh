#!/bin/bash
# vim: sts=4 sw=4 et

set -e
set -u

OUTDIR=examples-data

scriptpath=$(dirname $(realpath "${BASH_SOURCE[0]}"))
source $scriptpath/utils.sh

OWD=$(pwd)
rm -fr $OUTDIR
mkdir -p $OUTDIR/images
cd $OUTDIR/images

mkdir -p snapshots

(
  cd snapshots

  fake_image steamdeck snapshot 20181102.1 false
  fake_image steamdeck-beta snapshot 20181102.1 false
  fake_image steamdeck-rc snapshot 20220215.0 false
  fake_image atomic snapshot 20181102.1 false

  fake_image steamdeck snapshot 20181102.2 false
  fake_image atomic snapshot 20181102.2 false

  fake_image steamdeck snapshot 20181108.1 false
  fake_image steamdeck-beta snapshot 20181108.1 false
  fake_image atomic snapshot 20181108.1 false
)

mkdir -p releases

(
  cd releases

  fake_image steamdeck 3.1 20220401.1 false
  fake_image steamdeck 3.1 20220402.3 true
  fake_image steamdeck 3.2 20220411.1 false
  # Simulate an update that we don't want to propose anymore
  fake_image steamdeck 3.2 20220412.1 false true
  # Test the skip field explicitly set to false
  fake_image steamdeck 3.3 20220423.1 true false

  fake_image steamdeck-rc 3.1 20220401.5 false

  # Same checkpoint as in 'steamdeck'
  fake_image steamdeck-beta 3.1 20220402.3 true
  fake_image steamdeck-beta 3.1 20220405.100 false
  # The buildid of a checkpoint can be different, as long as they are
  # conceptually the same (i.e. introduce the same breaking changes)
  fake_image steamdeck-beta 3.3 20220423.100 true
  # Testing a new checkpoint that still hasn't been promoted to 'steamdeck'
  fake_image steamdeck-beta 3.4 20220501.100 true
)

mkdir -p releases-and-snaps

(
  cd releases-and-snaps

  fake_image steamdeck snapshot 20220201.1 false
  fake_image steamdeck snapshot 20220225.1 false
  fake_image steamdeck 3.0 20220303.2 false
  # Simulate an update that has been removed
  fake_image steamdeck 3.0 20220303.3 false true true

  fake_image steamdeck-rc 3.0 20220303.1 false

  fake_image steamdeck-beta snapshot 20220221.100 false
  fake_image steamdeck-beta 3.1 20220301.100 false

  fake_image steamdeck-main 3.1 20220302.1005 false
  fake_image steamdeck-main 3.2 20220304.1000 false
)

mkdir -p releases-and-snaps2

(
  cd releases-and-snaps2

  # Simulate the case where we had to set up a checkpoint before the
  # switch to versioned images was completed
  fake_image steamdeck snapshot 20230201.1 false
  fake_image steamdeck snapshot 20230303.1 true
  fake_image steamdeck 3.5 20230401.1 true
  fake_image steamdeck 3.5 20230411.1 false

  fake_image steamdeck-beta snapshot 20230303.100 true
  fake_image steamdeck-beta 3.5 20230401.100 true
  fake_image steamdeck-beta 3.6 20230727.100 false
)

mkdir -p releases-and-snaps3

(
  cd releases-and-snaps3

  fake_image steamdeck snapshot 20230502.1 false
  # This simulates a new stable hotfix release, still not versioned yet
  fake_image steamdeck snapshot 20230822.1 false

  fake_image steamdeck-rc snapshot 20230503.1 false

  fake_image steamdeck-beta 3.5 20230715.100 false
  fake_image steamdeck-beta 3.5 20230806.100 false

  fake_image steamdeck-bc 3.6 20230805.100 false

  fake_image steamdeck-main 3.5 20230714.1005 false
  fake_image steamdeck-main 3.6 20230804.1000 false
)

mkdir -p releases-and-snaps4

(
  cd releases-and-snaps4

  # This simulates the case where versioned images reached rel but we never
  # released an updated rc
  fake_image steamdeck 3.5 20230820.1 false

  fake_image steamdeck-rc snapshot 20220303.1 false

  fake_image steamdeck-beta 3.5 20230815.100 false
)

mkdir -p releases-and-snaps5

(
  cd releases-and-snaps5

  fake_image steamdeck snapshot 20230801.1 false

  fake_image steamdeck-rc snapshot 20220303.1 false

  fake_image steamdeck-beta 3.5 20230815.100 false
)

echo "Hierarchy created under '$OUTDIR/images'"

