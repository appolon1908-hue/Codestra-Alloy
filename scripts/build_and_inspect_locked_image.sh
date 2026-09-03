#!/usr/bin/env bash
set -Eeuo pipefail

manifest="codestra/release/image-build.v1.json"
runtime_lock="codestra/release/runtime-base.lock.json"
dockerfile="$(jq -er '.dockerfile | select(. == "codestra/deploy/Dockerfile")' "$manifest")"
context="$(jq -er '.context | select(. == ".")' "$manifest")"
builder="$(jq -er '.buildArgs.GO_BUILDER_IMAGE | select(type == "string")' "$manifest")"
runtime="$(jq -er '.buildArgs.ALLOY_BASE_IMAGE | select(type == "string")' "$manifest")"

jq -e '.buildArgs | keys == ["ALLOY_BASE_IMAGE", "GO_BUILDER_IMAGE"]' "$manifest" >/dev/null
[[ "$builder" =~ ^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$ ]]
[[ "$runtime" =~ ^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$ ]]
test "$builder" = "$(jq -er '.builderImage' "$runtime_lock")"
test "$runtime" = "$(jq -er '.runtimeBaseImage' "$runtime_lock")"

if [[ "${1:-}" == "--validate-manifest" ]]; then
  echo "ALLOY_IMAGE_BUILD_MANIFEST=PASS"
  exit 0
fi

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"
tag="local/codestra-alloy:${source_sha}"

docker build \
  --file "$dockerfile" \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "ALLOY_BASE_IMAGE=$runtime" \
  --tag "$tag" \
  "$context"
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
