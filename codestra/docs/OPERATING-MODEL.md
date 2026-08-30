# Codestra Alloy Operating Model

## Corporate role

Alloy is the Codestra server-side log collection agent. It tails approved service and container log files, reads the persistent journal only where allowed, applies bounded corporate labels, performs defense-in-depth redaction, and writes to the assigned Loki business tenant.

Alloy does not replace:

- Node Exporter for host metrics;
- cAdvisor for container metrics;
- OpenTelemetry Collector for application OTLP metrics, logs and traces;
- Prometheus for metrics, recording rules, SLOs and alert evaluation;
- Loki for log storage and query;
- Grafana for presentation;
- OpenBao for secrets and PKI.

It never performs business mutations, communications delivery, provider writes, identity administration, lending/funding actions or financial/trading actions.

## One business per instance

Every Alloy instance is assigned one `CODESTRA_BUSINESS`, one environment, one region, one canonical server and one immutable deployment ID. The deployment controller supplies those values. A workload or log line cannot select a different business tenant.

Approved businesses are:

- `platform`
- `codestra`
- `moneybee`
- `beyvra`
- `breero`
- `larim-a`
- `transportation`
- `booked4seasons`
- `social`
- `klyrow`
- `telnexa`
- `kyqra`
- `restaurant`
- `provisioning`

On a shared server, each business gets a separate host log root and separate Alloy instance. No Alloy instance may mount a parent directory containing another business.

## Approved log layout

The mounted root appears in the container as `/var/log/codestra` and contains only the assigned business:

```text
/var/log/codestra/
└── <application>/
    └── <service>/
        ├── application.log
        ├── audit.log
        └── docker/
            └── <explicitly-mounted-container>-json.log
```

Application and service directory names are controlled deployment metadata and become bounded Loki labels. Filenames and container IDs are removed from labels.

Container stdout/stderr collection uses explicit business-scoped bind mounts into the approved layout. The runtime deliberately does not mount `/var/run/docker.sock` or the global `/var/lib/docker/containers` tree. This prevents container-control authority and prevents shared-host business mixing.

Applications that emit OTLP use the Codestra OpenTelemetry Collector, not Alloy. Applications remain responsible for structured logging and data minimization.

## Journal policy

A platform Alloy instance on a dedicated or platform-owned host may mount the real persistent journal at `/run/log/journal`.

A business Alloy instance on a shared host mounts an approved empty directory at `/run/log/journal`. It must not read global system logs that may contain another business's data.

The machine ID is mounted read-only. Journal access must be proven using a least-privilege host ACL or group mapping; the Alloy container is never made privileged to bypass permissions.

## Non-root host access

Alloy runs as UID/GID `10001:10001`. Before activation, the operator must prove that this identity can read only:

- the assigned business log root;
- the approved journal directory for the selected profile;
- `/etc/machine-id`;
- its own durable Alloy storage volume.

The preferred approach is explicit host ACLs on the approved directories. World-readable logs, Docker-socket access, broad root groups, privileged mode, host PID namespace and host network are prohibited.

## Labels and structured fields

Every stream uses only:

- `codestra_business`
- `application`
- `service`
- `environment`
- `server`
- `region`
- `deployment`
- `log_source`

Customer, account, user, email, phone, request, correlation, trace, span, message, order, path, filename, container, image, pod and process identifiers are never stream labels.

Protected structured fields may include request, correlation, trace and span IDs when operationally necessary. They remain in the redacted log body for controlled search and correlation; they do not become labels.

## Redaction

Alloy applies defense-in-depth redaction before Loki write:

- private-key marker lines are dropped;
- authorization, cookie, password, token, API-key, client-secret, DSN and signing-key values are replaced;
- customer, account, user, email, phone, message, order, workflow and execution values are replaced;
- request/response body and database-statement values are replaced;
- standalone email addresses are replaced.

This is not permission to log sensitive data. Applications, gateways and the OpenTelemetry layer must prevent secrets and personal data at the source. Redaction fixtures must include JSON, logfmt, plain-text, multiline and malformed examples.

## Delivery and outage behavior

Alloy writes to a private TLS Loki endpoint and sets `tenant_id` from `CODESTRA_BUSINESS`. Client certificate, private key and CA are external runtime secret files.

The Loki writer uses a durable WAL and bounded retry/backoff. During a Loki outage, data accumulates only up to the configured disk and retention limits. Alloy must expose visible self-metrics for write failures, dropped entries, WAL state, file positions, process memory and CPU.

Alloy must never block a customer business transaction to preserve logs. When the WAL or disk limit is reached, loss must be visible and alertable; silent loss is a release blocker.

## Initial engineering objectives

Subject to staging calibration:

- private agent readiness at least 99.9%;
- zero public Alloy native listeners;
- zero Docker-socket or privileged access;
- zero unapproved cross-business file or journal reads;
- zero known credentials or raw customer payloads written to Loki;
- file-position recovery after restart without material duplication or omission;
- successful recovery from a 15-minute Loki outage within the approved WAL budget;
- WAL/storage use below 70% during normal operation and alerting at 80%;
- p95 collection-to-Loki delay below 30 seconds during expected peak load;
- self-metrics continuously scrapeable by Prometheus on the private network.

These are engineering objectives, not production SLOs until staging load and recovery evidence exists.

## Release evidence

Production promotion requires:

1. immutable builder, upstream and final image digests;
2. source-native Alloy configuration validation;
3. software bill of materials and vulnerability review;
4. business log-root allow/deny tests;
5. non-root ACL evidence;
6. journal boundary tests for platform and shared-host profiles;
7. Docker-socket and privileged-mode denial evidence;
8. representative redaction fixtures;
9. Loki mTLS, tenant-header and cross-business denial tests;
10. WAL restart, backend-outage and disk-capacity tests;
11. Prometheus self-metrics and alert coverage;
12. rollback instructions and previous image digest;
13. human production approval.

Promotion is:

```text
feature/* -> development -> test -> staging -> production -> main
```

The runtime remains `CONFIG_PREPARED_NOT_DEPLOYED`. Merge or CI success does not change server ACLs, mount logs, issue certificates, create networks, expose a port, start Alloy or activate Loki ingestion.
