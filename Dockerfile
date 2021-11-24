#
# Minimal build and deploy into a ubuntu/focal vm.
#
# build:
# -----
#   docker build -t steamos-atomupd:latest .
#
# run (server):
# ------------
#   # This assumes /path/to/server.conf references "/atompupd/data" as its root,
#   # maps the config file and relevant data directory into docker as read-only,
#   # and publishes the expected ports.
#   #
#   docker run --rm --init --name my-atomupd-server \
#              -v ./path/to/server.conf:/atomupd/server.conf:ro \
#              -v ./path/to/data/:/atomupd/data/:ro \
#              -p 8000:8000 -p 5000:5000 \
#              steamos-atomupd:latest -d -c /atomupd/server.conf
#
# launch shell against running:
# ----------------------
#   docker exec -ti my-atomupd-server bash

##
## Build image
##

FROM ubuntu:focal AS build

RUN apt-get update \
    && apt-get install -y \
       meson python3-flask python3-semantic-version \
    && rm -rf /var/lib/apt/lists/*

# Import working directory to /src/, build to /build/, install to /built/

COPY ./ /src/
RUN \
set -eu; \
cd /src; \
meson /build; \
ninja -C /build; \
meson test -v -C /build; \
DESTDIR=/built/ ninja -C /build install; \
:

##
## Run image
##

FROM ubuntu:focal

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
