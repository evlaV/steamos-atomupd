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

fake_image() {

    local product=$1
    local release=$2
    local variant=$3
    local arch=$4
    local version=$5
    local buildid=$6

    local imgdir imgname

    imgdir=$product/$release/$version/$arch
    imgname=$product-$release-$buildid-$version-$arch-$variant

    mkdir -p $imgdir
    make_manifest $product $release $variant $arch $version $buildid > \
        $imgdir/$imgname.manifest.json

    if [ "$variant" == "rauc" ]; then
        touch $imgdir/$imgname.raucb
	mkdir $imgdir/$imgname.castr
    fi
}

mkdir -p snapshots

(
  cd snapshots

  fake_image steamos clockwerk devel amd64 snapshot 20181102.1
  fake_image steamos clockwerk rauc  amd64 snapshot 20181102.1

  fake_image steamos clockwerk devel amd64 snapshot 20181102.2

  fake_image steamos clockwerk devel amd64 snapshot 20181108.1
  fake_image steamos clockwerk rauc  amd64 snapshot 20181108.1
)

mkdir -p releases

(
  cd releases

  fake_image steamos clockwerk devel amd64 3.0 20190211
  fake_image steamos clockwerk rauc  amd64 3.0 20190211

  fake_image steamos clockwerk devel amd64 3.1 20190101
  fake_image steamos clockwerk rauc  amd64 3.1 20190101
)

echo "Hierarchy created under '$OUTDIR/images'"
