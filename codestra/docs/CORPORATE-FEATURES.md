# Codestra Alloy Corporate Features

## Mission

Grafana Alloy is the standard telemetry agent profile for Codestra servers and container hosts. It collects logs, metrics and selected OTLP signals, normalizes Codestra metadata and forwards them to the approved observability backends.

## Reusable server profiles

Maintain reviewed profiles for edge, gateway, identity, Middleware, application, database, provider, contact-center and observability servers. Each profile defines only the receivers/collectors required for that server class.

## Corporate features

- systemd/Linux log collection;
- Docker/container log collection;
- Prometheus endpoint discovery/scraping where appropriate;
- OTLP receive/forward capability where required;
- canonical Codestra relabeling;
- deployment/version enrichment;
- secret/PII redaction before forwarding;
- buffering/retry/backpressure visibility;
- Alloy self-health metrics;
- environment-specific destinations;
- standardized drop filters for noisy/unneeded telemetry.

## Business representation

Every application/server profile attaches safe `codestra_business`, application, service, environment, server, region and deployment context. This lets one corporate Grafana instance show portfolio-level health while preserving drill-down to the affected business and service.

## Security

Alloy is an agent, not an Internet-facing product. Native administrative/diagnostic endpoints remain private. Runtime destination credentials are injected from OpenBao or approved secret files, never committed.

## Release rule

`allo.codestra.media` is an internal/private identity. Changes stay outside imported upstream source and are promoted only after config validation and staging evidence.
