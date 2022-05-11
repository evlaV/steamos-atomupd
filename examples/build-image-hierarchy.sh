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

    local variant=$1
    local version=$2
    local buildid=$3
    local checkpoint=$4
    local product=${5:-steamos}
    local release=${6:-holo}
    local arch=${7:-amd64}

    local imgdir imgname

    imgdir=$product/$release/$version/$arch
    imgname=$product-$release-$buildid-$version-$arch-$variant

    mkdir -p "$imgdir"
    if [ "$checkpoint" == "1" ]; then
        make_checkpoint "$product" "$release" "$variant" "$arch" "$version" "$buildid" > \
            "$imgdir/$imgname.manifest.json"
    else
        make_manifest "$product" "$release" "$variant" "$arch" "$version" "$buildid" > \
            "$imgdir/$imgname.manifest.json"
    fi

    touch "$imgdir/$imgname.raucb"
    mkdir "$imgdir/$imgname.castr"
}

mkdir -p snapshots

(
  cd snapshots

  fake_image steamdeck snapshot 20181102.1 0
  fake_image steamdeck-beta snapshot 20181102.1 0
  fake_image steamdeck-rc snapshot 20220215.0 0
  fake_image atomic snapshot 20181102.1 0

  fake_image steamdeck snapshot 20181102.2 0
  fake_image atomic snapshot 20181102.2 0

  fake_image steamdeck snapshot 20181108.1 0
  fake_image steamdeck-beta snapshot 20181108.1 0
  fake_image atomic snapshot 20181108.1 0
)

mkdir -p releases

(
  cd releases

  fake_image steamdeck 3.1 20220401.1 0
  fake_image steamdeck 3.1 20220402.3 1
  fake_image steamdeck 3.2 20220411.1 0
  fake_image steamdeck 3.3 20220423.1 1

  fake_image steamdeck-rc 3.1 20220401.5 0

  # Same checkpoint as in 'steamdeck'
  fake_image steamdeck-beta 3.1 20220402.3 1
  fake_image steamdeck-beta 3.1 20220405.100 0
  # The buildid of a checkpoint can be different, as long as they are
  # conceptually the same (i.e. introduce the same breaking changes)
  fake_image steamdeck-beta 3.3 20220423.100 1
  # Testing a new checkpoint that still hasn't been promoted to 'steamdeck'
  fake_image steamdeck-beta 3.4 20220501.100 1
)

mkdir -p releases-and-snaps

(
  cd releases-and-snaps

  fake_image steamdeck snapshot 20220201.1 0
  fake_image steamdeck snapshot 20220225.1 0
  fake_image steamdeck 3.0 20220303.2 0

  fake_image steamdeck-rc 3.0 20220303.1 0

  fake_image steamdeck-beta snapshot 20220221.100 0
  fake_image steamdeck-beta 3.1 20220301.100 0

  fake_image steamdeck-main 3.1 20220302.1005 0
  fake_image steamdeck-main 3.2 20220304.1000 0
)

echo "Hierarchy created under '$OUTDIR/images'"
