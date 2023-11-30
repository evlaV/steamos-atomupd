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

mkdir -p releases-checkpoints

(
  cd releases-checkpoints

  fake_image steamdeck 3.6 20231112.1
  # Simulate an image that requires a checkpoint zero and provides directly
  # the checkpoint 2
  fake_image steamdeck 3.6 20231114.1 2 0
  fake_image steamdeck 3.6 20231115.1 0 2

  fake_image steamdeck-beta 3.6 20231113.100 1 0
  fake_image steamdeck-beta 3.6 20231113.101 2 1
)

mkdir -p releases-retired-checkpoint

(
  cd releases-retired-checkpoint

  fake_image steamdeck 3.6 20231112.1
  # Simulate a checkpoint that was quickly retired by using the "skip" option
  # and substituted with another one
  fake_image steamdeck 3.6 20231113.1 1 0 true
  fake_image steamdeck 3.6 20231113.2 1 0
  fake_image steamdeck 3.6 20231120.1 0 1
)

mkdir -p releases

(
  cd releases

  fake_image steamdeck 3.1 20220401.1 false
  fake_image steamdeck 3.1 20220402.3 1 0
  fake_image steamdeck 3.2 20220411.1 0 1
  # Simulate an update that we don't want to propose anymore
  fake_image steamdeck 3.2 20220412.1 0 1 true
  # Test the skip field explicitly set to false
  fake_image steamdeck 3.3 20220423.1 2 1 false

  fake_image steamdeck-rc 3.1 20220401.5 false

  # Same checkpoint as in 'steamdeck'
  fake_image steamdeck-beta 3.1 20220402.3 1 0
  fake_image steamdeck-beta 3.1 20220405.100 0 1
  fake_image steamdeck-beta 3.3 20220423.100 2 1
  # Testing a new checkpoint that still hasn't been promoted to 'steamdeck'
  fake_image steamdeck-beta 3.4 20220501.100 3 2
)

mkdir releases2

(
  cd releases2

  fake_image steamdeck 3.5 20230403.1
  fake_image steamdeck 3.5 20230404.1 1 0
  fake_image steamdeck 3.5 20230411.1 0 1
  # This is a shadow checkpoint
  fake_image steamdeck 3.6 20230423.1 3 1 false true true
  fake_image steamdeck 3.6 20230425.1 0 3

  fake_image steamdeck-beta 3.5 20230402.100 1 0
  # Simulate a checkpoint 2 and then a checkpoint 3 that reverts it.
  # This is signaled by the fact that in "steamdeck" we have a shadow checkpoint
  # for those two.
  fake_image steamdeck-beta 3.6 20230412.100 2 1
  fake_image steamdeck-beta 3.6 20230412.101 0 2
  fake_image steamdeck-beta 3.6 20230413.100 3 2
)

mkdir -p releases3

(
  cd releases3

  fake_image steamdeck 3.5 20230403.1
  fake_image steamdeck 3.5 20230404.1 1 0
  fake_image steamdeck 3.5 20230411.1 0 1

  fake_image steamdeck-staging 3.5 20230501.10000 0 1
  fake_image steamdeck-staging 3.5 20230507.10000 2 1
)

mkdir -p releases4

(
  cd releases4

  fake_image steamdeck 3.5 20230404.1 1 0
  fake_image steamdeck 3.5 20230411.1 0 1
  # Shadow checkpoint
  fake_image steamdeck 3.6 20230508.1 2 1 false true true

  fake_image steamdeck-staging 3.5 20230501.10000 0 1
  fake_image steamdeck-staging 3.6 20230507.10000 2 1
)

mkdir -p releases5

(
  cd releases5

  fake_image steamdeck 3.5 20230404.1
  fake_image steamdeck 3.5 20230411.1 1 0
  fake_image steamdeck 3.5 20230412.1 0 1
  fake_image steamdeck 3.6 20230413.1 0 1

  fake_image steamdeck-beta 3.5 20230405.100
  fake_image steamdeck-beta 3.5 20230405.101 1 0
  fake_image steamdeck-beta 3.5 20230406.100 0 1
  fake_image steamdeck-beta 3.6 20230421.100 0 1
  fake_image steamdeck-beta 3.6 20230422.100 0 1
)

mkdir -p releases-and-snaps

(
  cd releases-and-snaps

  fake_image steamdeck snapshot 20220201.1 false
  fake_image steamdeck snapshot 20220225.1 false
  fake_image steamdeck 3.0 20220303.2 false
  # Simulate an update that has been removed
  fake_image steamdeck 3.0 20220303.3 false false true true

  fake_image steamdeck-rc 3.0 20220303.1 false

  fake_image steamdeck-beta snapshot 20220221.100 false
  fake_image steamdeck-beta 3.1 20220301.100 false

  fake_image steamdeck-main 3.1 20220302.1005 false
  fake_image steamdeck-main 3.2 20220304.1000 false
)

mkdir -p releases-and-snaps2

(
  cd releases-and-snaps2

  fake_image steamdeck snapshot 20230201.1 false
  fake_image steamdeck 3.5 20230303.1 false
  fake_image steamdeck 3.5 20230401.1 1 0
  fake_image steamdeck 3.5 20230411.1 0 1

  fake_image steamdeck-beta snapshot 20230303.100 false
  fake_image steamdeck-beta 3.5 20230401.100 1 0
  fake_image steamdeck-beta 3.6 20230727.100 0 1
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
  fake_image steamdeck 3.5 20230820.1

  fake_image steamdeck-rc snapshot 20220303.1

  fake_image steamdeck-beta 3.5 20230815.100
)

mkdir -p releases-and-snaps5

(
  cd releases-and-snaps5

  fake_image steamdeck snapshot 20230801.1

  fake_image steamdeck-rc snapshot 20220303.1

  fake_image steamdeck-beta 3.5 20230815.100
)

mkdir -p unexpected-manifest

(
  cd unexpected-manifest

  fake_image steamdeck 3.6.1 20231104.1
  # Image manifest that is unexpectedly empty
  touch steamos/holo/3.6.1/amd64/steamos-holo-20231104.2-3.6.1-amd64-steamdeck.manifest.json
)

echo "Hierarchy created under '$OUTDIR/images'"

