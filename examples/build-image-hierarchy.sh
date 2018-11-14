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

    local imgdir manifname

    if [ "$INCLUDE_RELEASE" ]; then
        imgdir=$product/$release/$version/$arch
        manifname=$product-$release-$version-$arch-$variant.manifest.json
    else
        imgdir=$product/$version/$arch
        manifname=$product-$version-$arch-$variant.manifest.json
    fi

    mkdir -p $imgdir
    make_manifest $product $release $version $arch $variant > $imgdir/$manifname

    if [ "$variant" == "rauc" ]; then
        mkdir $imgdir/rauc
        touch $imgdir/rauc/casync-bundle.raucb
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
