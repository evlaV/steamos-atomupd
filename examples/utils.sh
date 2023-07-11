#!/bin/bash
# vim: sts=4 sw=4 et

make_manifest() {
    cat << EOF
{
  "product": "$1",
  "release": "$2",
  "variant": "$3",
  "arch": "$4",
  "version": "$5",
  "buildid": "$6",
  "checkpoint": $7,
  "skip": $8
}
EOF
}

fake_image() {

    local -r variant=$1
    local -r version=$2
    local -r buildid=$3
    local -r checkpoint=$4
    local -r skip=${5:-false}
    local -r deleted=${6:-false}
    local -r product=steamos
    local -r release=holo
    local -r arch=amd64

    local imgdir imgname

    imgdir=$product/$release/$version/$arch
    imgname=$product-$release-$buildid-$version-$arch-$variant

    mkdir -p "$imgdir"
    make_manifest "$product" "$release" "$variant" "$arch" "$version" "$buildid" "$checkpoint" "$skip" > \
      "$imgdir/$imgname.manifest.json"

    if [ "$deleted" == true ]; then
      # Do not create the RAUC bundle file and the directory with the chunks,
      # as if they were removed to prevent an image to ever be installed
      return
    fi

    if [ -f "${OWD}/examples/rauc/$imgname.raucb" ]; then
      # Use the mock raucb, if available
      ln -s "${OWD}/examples/rauc/$imgname.raucb" "$imgdir/$imgname.raucb"
    else
      touch "$imgdir/$imgname.raucb"
    fi

    mkdir "$imgdir/$imgname.castr"
}
