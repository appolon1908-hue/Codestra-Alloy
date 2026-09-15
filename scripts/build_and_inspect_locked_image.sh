#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

builder="$(jq -r '.builderImage' codestra/release/runtime-base.lock.json)"
runtime="$(jq -r '.runtimeBaseImage' codestra/release/runtime-base.lock.json)"
tag="local/codestra-alloy:${source_sha}"

docker build \
  --file codestra/deploy/Dockerfile \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "ALLOY_BASE_IMAGE=$runtime" \
  --tag "$tag" \
  .
docker run --rm "$tag" --version

container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then
    docker container rm "$container_id" >/dev/null
  fi
}
trap cleanup EXIT
container_id="$(docker create "$tag")"
lock_copy="${RUNNER_TEMP:-/tmp}/alloy-source-lock-${source_sha}.json"
docker cp "$container_id:/usr/share/codestra/CODESTRA_UPSTREAM_LOCK.json" "$lock_copy"
cmp CODESTRA_UPSTREAM_LOCK.json "$lock_copy"
echo "ALLOY_LOCKED_IMAGE_INSPECTION=PASS"
