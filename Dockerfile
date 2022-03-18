#
# Minimal build and deploy into a Debian container.
#
# build:
# -----
#   docker build -t steamos-atomupd:latest .
#
# run (server):
# ------------
#   # This assumes /path/to/server.conf references "/atomupd/data" as its root,
#   # maps the config file and relevant data directory into docker as read-only,
#   # and publishes the expected ports.
#   #
#   docker run --rm --init --name my-atomupd-server \
#              -v ./path/to/server.conf:/atomupd/server.conf:ro \
#              -v ./path/to/data/:/atomupd/data/:ro \
#              -p 8000:8000 -p 5000:5000 \
#              steamos-atomupd:latest -d -c /atomupd/server.conf
#
# launch shell against a running server:
# -------------------------------------
#   docker exec -ti my-atomupd-server bash
#
# run (export metadata for static server):
# ----------------------------------------
#   # This assumes /path/to/server.conf references "/atomupd/data" as its root.
#   # The metadata export writes to the current working directory, so we set
#   # /atomupd/meta to be the current working directory.
#   #
#   # /path/to/data must be published by a web server as the ImagesUrl.
#   # /path/to/meta must be published by a web server as the MetaUrl.
#   #
#   docker run --rm --init --name my-atomupd-staticserver \
#              -v ./path/to/server.conf:/atomupd/server.conf:ro \
#              -v ./path/to/data/:/atomupd/data/:ro \
#              -v ./path/to/meta/:/atomupd/meta/:rw \
#              -w /atomupd/meta \
#              --entrypoint /usr/local/bin/steamos-atomupd-staticserver \
#              steamos-atomupd:latest -d -c /atomupd/server.conf
#
#   # To test the static server:
#   mkdir tmp
#   docker run --rm --name my-atomupd-staticserver \
#              -v $(pwd)/examples/server-releases.conf:/atomupd/server.conf:ro \
#              -v $(pwd)/examples/examples-data:/atomupd/data/examples-data:ro \
#              -v $(pwd)/tmp:/atomupd/data:rw \
#              -w /atomupd/data \
#              --entrypoint /usr/local/bin/steamos-atomupd-staticserver \
#              steamos-atomupd:latest -d -c /atomupd/server.conf
#    # There should be no difference
#    diff -ru tests/staticexpected/steamos tmp/steamos

##
## Build image
##

FROM debian:bullseye-slim AS build

RUN apt-get update \
    && apt-get install -y \
       meson python3-flask python3-semantic-version \
    && rm -rf /var/lib/apt/lists/*

# Import working directory to /src/, build to /build/, install to /built/

COPY ./ /src/
RUN \
set -eu; \
cd /src; \
meson setup /build; \
DESTDIR=/built/ meson install -C /build; \
:

##
## Run image
##

FROM debian:bullseye-slim

ARG BUILD_ID=""
ARG IMAGE_ID="steamos-atomupd"
ARG IMAGE_NAME="steamos-atomupd"
ARG IMAGE_VERSION=""

# Minus build-only deps
RUN \
set -eu; \
apt-get update; \
apt-get install -y python3-flask python3-semantic-version; \
rm -rf /var/lib/apt/lists/*; \
install -d /atomupd/data; \
if [ -n "${IMAGE_NAME-}" ]; then \
    echo "$IMAGE_NAME" >> /etc/issue; \
    echo "$IMAGE_NAME" > /etc/debian_chroot; \
fi; \
if [ -n "${IMAGE_ID-}" ]; then \
    echo "IMAGE_ID=$IMAGE_ID" >> /usr/lib/os-release; \
fi; \
if [ -n "${IMAGE_VERSION-}" ]; then \
    echo "IMAGE_VERSION=$IMAGE_VERSION" >> /usr/lib/os-release; \
fi; \
if [ -n "${BUILD_ID-}" ]; then \
    echo "BUILD_ID=$BUILD_ID" >> /usr/lib/os-release; \
fi; \
head -v -n-0 /etc/debian_chroot /etc/issue /usr/lib/os-release || :; \
:

# Copy install from build image into place
COPY --from=build /built/ /

# Use the non-standard pythonpath we install to
ENV PYTHONPATH=/usr/local/lib/python3/dist-packages/

STOPSIGNAL SIGINT

ENTRYPOINT [ "/usr/local/bin/steamos-atomupd-server" ]
EXPOSE 5000
