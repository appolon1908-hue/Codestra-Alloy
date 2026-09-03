# syntax=docker.io/docker/dockerfile@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG GO_BUILDER_IMAGE
ARG ALLOY_BASE_IMAGE

# Build the executable from the repository's verified, sanitized upstream tree.
# The approved builder contains the C toolchain and libsystemd development files
# required by the real journal implementation. The runtime base is only an
# OS/library substrate; its bundled Alloy executable is overwritten.
FROM ${GO_BUILDER_IMAGE} AS alloy-builder
COPY upstream /src/upstream
WORKDIR /src/upstream/collector
RUN CGO_ENABLED=1 GOOS=linux go build \
      -buildvcs=false \
      -trimpath \
      -tags='promtail_journal_enabled' \
      -ldflags='-s -w -buildid=' \
      -o /out/alloy \
      .

WORKDIR /src
COPY codestra/deploy/healthcheck.go ./healthcheck.go
RUN CGO_ENABLED=0 GOOS=linux go build \
      -buildvcs=false \
      -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/alloy-healthcheck \
      ./healthcheck.go

COPY codestra/deploy/readonly_proxy.go ./readonly_proxy.go
RUN CGO_ENABLED=0 GOOS=linux go build \
      -buildvcs=false \
      -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/alloy-readonly-proxy \
      ./readonly_proxy.go

FROM ${ALLOY_BASE_IMAGE}
LABEL org.opencontainers.image.title="Codestra Corporate Alloy"
LABEL org.opencontainers.image.description="Business-scoped, non-privileged host and service log collection for Codestra"
LABEL org.opencontainers.image.vendor="Codestra"
LABEL codestra.source.authority="vendored-verified-upstream-tree"
LABEL codestra.runtime.base-role="runtime-substrate-only"
LABEL codestra.feature.systemd-journal="promtail_journal_enabled"

# The final /bin/alloy is always the binary compiled above from this repository's
# exact imported tree. The executable inherited from ALLOY_BASE_IMAGE is replaced.
USER 0:0
COPY --from=alloy-builder --chown=10001:10001 --chmod=0555 /out/alloy /bin/alloy
COPY --from=alloy-builder --chown=10001:10001 --chmod=0555 /out/alloy-healthcheck /alloy-healthcheck
COPY --from=alloy-builder --chown=10001:10001 --chmod=0555 /out/alloy-readonly-proxy /alloy-readonly-proxy
COPY --chown=10001:10001 --chmod=0444 CODESTRA_UPSTREAM_LOCK.json /usr/share/codestra/CODESTRA_UPSTREAM_LOCK.json
COPY --chown=10001:10001 --chmod=0444 codestra/source-image-contract.v1.json /usr/share/codestra/source-image-contract.v1.json
COPY --chown=10001:10001 --chmod=0444 codestra/config.alloy /etc/alloy/config.alloy

# The official Alloy image seeds /var/lib/alloy as UID/GID 473. Codestra runs
# the final process as 10001, so prepare the image-backed volume seed with the
# same identity that will write WAL and component state at runtime.
RUN chown -R 10001:10001 /var/lib/alloy \
    && chmod -R u+rwX,g+rwX,o-rwx /var/lib/alloy

USER 10001:10001
