#!/bin/bash

set -e
set -u

[ -d examples ] || exit 1

rm -fr examples/images
mkdir examples/images
cd examples/images

make_manifest() {

    local product=$1
    local release=$2
    local version=$3
    local arch=$4
    local variant=$5

    cat << EOF
{
  "product": "$product",
  "release": "$release",
  "arch": "$arch",
  "version": "$version",
  "variant": "$variant"
}
EOF
}

fake_image() {

    local product=$1
    local release=$2
    local version=$3
    local arch=$4
    local variant=$5

    local imgdir imgname

    if [ "$INCLUDE_RELEASE" ]; then
        imgdir=$product/$release/$version/$arch
	imgname=$product-$release-$version-$arch-$variant
    else
        imgdir=$product/$version/$arch
        imgname=$product-$version-$arch-$variant
    fi

    mkdir -p $imgdir
    make_manifest $product $release $version $arch $variant > $imgdir/$imgname.manifest.json

    if [ "$variant" == "rauc" ]; then
        touch $imgdir/$imgname.raucb
	mkdir $imgdir/$imgname.castr
    fi
}

mkdir -p daily

(
  cd daily

  INCLUDE_RELEASE=yep

  fake_image steamos clockwerk 20181102.1 amd64 devel
  fake_image steamos clockwerk 20181102.1 amd64 rauc

  fake_image steamos clockwerk 20181102.2 amd64 devel

  fake_image steamos clockwerk 20181108.1 amd64 devel
  fake_image steamos clockwerk 20181108.1 amd64 rauc
)

mkdir -p releases

(
  cd releases

  INCLUDE_RELEASE=

  fake_image steamos clockwerk 3.0 amd64 devel
  fake_image steamos clockwerk 3.0 amd64 rauc

  fake_image steamos clockwerk 3.1 amd64 devel
  fake_image steamos clockwerk 3.1 amd64 rauc
)

echo "Hierarchy created under 'examples/images'"
