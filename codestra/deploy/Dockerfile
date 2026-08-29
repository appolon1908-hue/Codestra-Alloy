# syntax=docker/dockerfile:1.7

ARG GO_BUILDER_IMAGE
ARG ALLOY_BASE_IMAGE

FROM ${GO_BUILDER_IMAGE} AS healthcheck-builder
WORKDIR /src
COPY codestra/deploy/healthcheck.go ./healthcheck.go
RUN CGO_ENABLED=0 GOOS=linux go build \
      -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/alloy-healthcheck \
      ./healthcheck.go

FROM ${ALLOY_BASE_IMAGE}
LABEL org.opencontainers.image.title="Codestra Corporate Alloy"
LABEL org.opencontainers.image.description="Business-scoped, non-privileged host and service log collection for Codestra"
LABEL org.opencontainers.image.vendor="Codestra"

COPY --from=healthcheck-builder --chown=10001:10001 --chmod=0555 /out/alloy-healthcheck /alloy-healthcheck
COPY --chown=10001:10001 --chmod=0444 codestra/config.alloy /etc/alloy/config.alloy

USER 10001:10001
