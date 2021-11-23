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
RUN cd /src \
    && meson /build \
    && ninja -C /build \
    && meson test -v -C /build \
    && DESTDIR=/built/ ninja -C /build install

##
## Run image
##

FROM ubuntu:focal

# Minus build-only deps
RUN apt-get update && \
    apt-get install -y python3-flask python3-semantic-version && \
    rm -rf /var/lib/apt/lists/* && \
    install -d /atomupd/data && \
    :

# Copy install from build image into place
COPY --from=build /built/ /

# Use the non-standard pythonpath we install to
ENV PYTHONPATH=/usr/local/lib/python3/dist-packages/

STOPSIGNAL SIGINT

ENTRYPOINT [ "/usr/local/bin/steamos-atomupd-server" ]
