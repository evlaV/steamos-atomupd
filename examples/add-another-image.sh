#!/bin/bash
# vim: sts=4 sw=4 et

set -e
set -u

OUTDIR=examples-data

scriptpath=$(dirname $(realpath "${BASH_SOURCE[0]}"))
source $scriptpath/utils.sh

OWD=$(pwd)
cd $OUTDIR/images

(
  cd releases

  fake_image steamdeck 3.5 20230705.1 3 2
)

touch releases/steamos/updated.txt

echo "Hierarchy updated under '$OUTDIR/images'"

