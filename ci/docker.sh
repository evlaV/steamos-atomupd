#!/bin/sh
# Copyright 2021 Collabora Ltd
# SPDX-License-Identifier: MIT

# This is executed by busybox sh, which we know does support echo -n:
# shellcheck disable=SC3037
# Deliberately avoiding [:upper:], [:lower:], we specifically want ASCII:
# shellcheck disable=SC2018
# shellcheck disable=SC2019

set -eux

mkdir -p /kaniko/.docker
echo "{\"auths\":{\"$CI_REGISTRY\":{\"auth\":\"$(echo -n "$CI_REGISTRY_USER:$CI_REGISTRY_PASSWORD" | base64)\"}}}" > /kaniko/.docker/config.json

# e.g. 0.20190724.0-48-g2aad2e3
BUILD_ID="$(tr A-Z a-z < VERSION | tr -d '\n' | tr -c 'a-z0-9._-' '_')"

if [ -n "${CI_PIPELINE_ID-}" ]; then
    # e.g. 0.20190724.0-48-g2aad2e3-ci12345
    BUILD_ID="${BUILD_ID}-ci${CI_PIPELINE_ID}"
fi

# e.g. steam_steamos-atomupd
IMAGE_ID="$(echo "${CI_PROJECT_PATH}/server" | tr A-Z a-z | tr -d '\n' | tr -c 'a-z0-9._-' '_')"
IMAGE_NAME="${CI_PROJECT_PATH}/server:$BUILD_ID"
IMAGE_VERSION="$BUILD_ID"

set --

if [ -n "${CI_REGISTRY_IMAGE-}" ]; then
    set -- "$@" --destination "$CI_REGISTRY_IMAGE/server:$BUILD_ID"

    if [ -n "${CI_COMMIT_TAG-}" ]; then
        set -- "$@" --destination "$CI_REGISTRY_IMAGE/server:latest"
    elif [ "${CI_COMMIT_BRANCH-}" = "${CI_DEFAULT_BRANCH}" ]; then
        set -- "$@" --destination "$CI_REGISTRY_IMAGE/server:$CI_COMMIT_BRANCH"
    else
        # This can be prefixed with ": " to force development builds to
        # be pushed if you need to exercise the whole pipeline
        set -- "$@" --no-push
    fi
else
    # Just build the image, we can't push it
    set -- "$@" --no-push
fi

/kaniko/executor \
    --build-arg BUILD_ID="$BUILD_ID" \
    --build-arg IMAGE_ID="$IMAGE_ID" \
    --build-arg IMAGE_NAME="$IMAGE_NAME" \
    --build-arg IMAGE_VERSION="$IMAGE_VERSION" \
    --context "$CI_PROJECT_DIR" \
    --dockerfile "$CI_PROJECT_DIR/Dockerfile" \
    "$@"

# vim:set sw=4 sts=4 et:
