#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

manifest="codestra/release/image-build.v1.json"
dockerfile="$(jq -er '.dockerfile | select(type == "string" and length > 0)' "$manifest")"
context="$(jq -er '.context | select(type == "string" and length > 0)' "$manifest")"
test -f "$dockerfile"
test -d "$context"
builder="$(jq -r '.builderImage' codestra/release/runtime-base.lock.json)"
runtime="$(jq -r '.runtimeBaseImage' codestra/release/runtime-base.lock.json)"
tag="local/codestra-alloy:${source_sha}"

docker build \
  --file "$dockerfile" \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "ALLOY_BASE_IMAGE=$runtime" \
  --tag "$tag" \
  "$context"
docker run --rm "$tag" --version

container_id=""
proxy_container_id=""
probe_network="codestra-alloy-readonly-${source_sha:0:12}-${GITHUB_RUN_ID:-local}"
probe_network_created="false"
cleanup() {
  if [[ -n "$proxy_container_id" ]]; then
    docker container rm --force "$proxy_container_id" >/dev/null
  fi
  if [[ "$probe_network_created" == "true" ]]; then
    docker network rm "$probe_network" >/dev/null
  fi
  if [[ -n "$container_id" ]]; then
    docker container rm "$container_id" >/dev/null
  fi
}
trap cleanup EXIT
container_id="$(docker create "$tag")"
lock_copy="${RUNNER_TEMP:-/tmp}/alloy-source-lock-${source_sha}.json"
docker cp "$container_id:/usr/share/codestra/CODESTRA_UPSTREAM_LOCK.json" "$lock_copy"
cmp CODESTRA_UPSTREAM_LOCK.json "$lock_copy"

docker network create --internal "$probe_network" >/dev/null
probe_network_created="true"
proxy_container_id="$(docker run --detach --network "$probe_network" \
  --network-alias alloy-readonly --read-only \
  --cap-drop ALL --security-opt no-new-privileges \
  --entrypoint /alloy-readonly-proxy "$tag")"
proxy_ready="false"
for _ in $(seq 1 20); do
  if docker run --rm --network "$probe_network" \
    --env ALLOY_HEALTHCHECK_URL=http://alloy-readonly:12346/-/reload \
    --env ALLOY_HEALTHCHECK_EXPECT_STATUS=403 \
    --entrypoint /alloy-healthcheck "$tag"; then
    proxy_ready="true"
    break
  fi
  sleep 1
done
test "$proxy_ready" = "true"
for route in /-/reload /-/support; do
  if docker run --rm --network "$probe_network" \
    --env "ALLOY_HEALTHCHECK_URL=http://alloy-readonly:12345${route}" \
    --entrypoint /alloy-healthcheck "$tag"; then
    echo "native Alloy administrative route was reachable from a network peer" >&2
    exit 1
  fi
done
for route in /-/support; do
  docker run --rm --network "$probe_network" \
    --env "ALLOY_HEALTHCHECK_URL=http://alloy-readonly:12346${route}" \
    --env ALLOY_HEALTHCHECK_EXPECT_STATUS=403 \
    --entrypoint /alloy-healthcheck "$tag"
done
docker run --rm --network "$probe_network" \
  --env ALLOY_HEALTHCHECK_URL=http://alloy-readonly:12346/-/reload \
  --env ALLOY_HEALTHCHECK_METHOD=POST \
  --env ALLOY_HEALTHCHECK_EXPECT_STATUS=403 \
  --entrypoint /alloy-healthcheck "$tag"
docker run --rm --network "$probe_network" \
  --env ALLOY_HEALTHCHECK_URL=http://alloy-readonly:12346/metrics \
  --env ALLOY_HEALTHCHECK_EXPECT_STATUS=502 \
  --entrypoint /alloy-healthcheck "$tag"
echo "ALLOY_LOCKED_IMAGE_INSPECTION=PASS"
