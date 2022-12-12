#!/bin/bash
# vim: sts=4 sw=4 et

set -e
set -u

OUTDIR=examples-data

OWD=$(pwd)
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
  "buildid": "$6",
  "checkpoint": $7
}
EOF
}

fake_image() {

    local -r variant=$1
    local -r version=$2
    local -r buildid=$3
    local -r checkpoint=$4
    local -r product=steamos
    local -r release=holo
    local -r arch=amd64

    local imgdir imgname

    imgdir=$product/$release/$version/$arch
    imgname=$product-$release-$buildid-$version-$arch-$variant

    mkdir -p "$imgdir"
    make_manifest "$product" "$release" "$variant" "$arch" "$version" "$buildid" "$checkpoint" > \
      "$imgdir/$imgname.manifest.json"

    if [ -f "${OWD}/examples/rauc/$imgname.raucb" ]; then
      # Use the mock raucb, if available
      ln -s "${OWD}/examples/rauc/$imgname.raucb" "$imgdir/$imgname.raucb"
    else
      touch "$imgdir/$imgname.raucb"
    fi

    mkdir "$imgdir/$imgname.castr"
}

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
  fake_image steamdeck 3.3 20220423.1 true

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

  fake_image steamdeck-rc 3.0 20220303.1 false

  fake_image steamdeck-beta snapshot 20220221.100 false
  fake_image steamdeck-beta 3.1 20220301.100 false

  fake_image steamdeck-main 3.1 20220302.1005 false
  fake_image steamdeck-main 3.2 20220304.1000 false
)

echo "Hierarchy created under '$OUTDIR/images'"
