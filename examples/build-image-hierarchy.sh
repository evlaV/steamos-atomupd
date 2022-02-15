#!/bin/bash
# vim: sts=4 sw=4 et

set -e
set -u

OUTDIR=examples-data

rm -fr $OUTDIR
mkdir -p $OUTDIR/images
cd $OUTDIR/images

make_manifest() {
    cat << EOF
{
  "product": "$1",
  "release": "$2",
  "variant": "$3",
  "arch": "$4",
  "version": "$5",
  "buildid": "$6"
}
EOF
}

make_checkpoint() {
    cat << EOF
{
  "product": "$1",
  "release": "$2",
  "variant": "$3",
  "arch": "$4",
  "version": "$5",
  "buildid": "$6",
  "checkpoint": true
}
EOF

}

fake_image() {

    local product=$1
    local release=$2
    local variant=$3
    local arch=$4
    local version=$5
    local buildid=$6
    local checkpoint=$7

    local imgdir imgname

    imgdir=$product/$release/$version/$arch
    imgname=$product-$release-$buildid-$version-$arch-$variant

    mkdir -p $imgdir
    if [ "$checkpoint" == "1" ]; then
        make_checkpoint $product $release $variant $arch $version $buildid > \
            $imgdir/$imgname.manifest.json
    else
        make_manifest $product $release $variant $arch $version $buildid > \
            $imgdir/$imgname.manifest.json
    fi

    touch $imgdir/$imgname.raucb
    mkdir $imgdir/$imgname.castr
}

mkdir -p snapshots

(
  cd snapshots

  fake_image steamos holo steamdeck amd64 snapshot 20181102.1 0
  fake_image steamos holo steamdeck-beta amd64 snapshot 20181102.1 0
  fake_image steamos holo steamdeck-rc amd64 snapshot 20220215.0 0
  fake_image steamos holo atomic amd64 snapshot 20181102.1 0

  fake_image steamos holo steamdeck amd64 snapshot 20181102.2 0
  fake_image steamos holo atomic amd64 snapshot 20181102.2 0

  fake_image steamos holo steamdeck amd64 snapshot 20181108.1 0
  fake_image steamos holo steamdeck-beta amd64 snapshot 20181108.1 0
  fake_image steamos holo atomic amd64 snapshot 20181108.1 0
)

mkdir -p releases

(
  cd releases

  fake_image steamos holo steamdeck amd64 3.0 20190211 0
  fake_image steamos holo steamdeck-beta  amd64 3.0 20190211 0
  fake_image steamos holo atomic amd64 3.0 20190211 0

  # Add a checkpoint after 3.0 but before 3.1 regular release
  fake_image steamos holo steamdeck amd64 3.1 20190101 1
  fake_image steamos holo steamdeck-beta amd64 3.1 20190101 1
  fake_image steamos holo atomic amd64 3.1 20190101 1

  fake_image steamos holo steamdeck amd64 3.1 20190201 0
  fake_image steamos holo steamdeck-beta  amd64 3.1 20190201 0
  fake_image steamos holo atomic amd64 3.1 20190201 0

  fake_image steamos holo steamdeck amd64 3.1 20190312 0
)

echo "Hierarchy created under '$OUTDIR/images'"
