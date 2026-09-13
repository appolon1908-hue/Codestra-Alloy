# Kyyow integration

This repository is the source authority for **alloy** in the Kyyow platform. Its Kyyow boundary is machine-readable in [kyyow-integration.v1.json](kyyow-integration.v1.json).

The component is **private** and its native ports are not made public by this contract. Keycloak owns identity, OpenBao owns secret delivery, and Middleware remains the sole writer to Odoo. Grafana and Superset consume read-only data paths.

This contract is source-complete but deliberately does not claim a live deployment. Production activation requires an immutable image/configuration digest, private-network verification, restore and rollback evidence, and a separately approved cutover.

## Source topology and limits

`codestra/config.alloy` contains file/journal sources, log processing and a Loki writer. It has no Prometheus scraping or OTLP receivers. `codestra/deploy/alloy_entrypoint.go` listens on 12345 and forwards allowed read routes to `127.0.0.1:12346`; the candidate Compose file exposes only 12345. Telemetry routes directly to Loki/Tempo and exporters are scraped by Prometheus.

All listed ports are private or loopback. This correction does not authorize runtime activation.
