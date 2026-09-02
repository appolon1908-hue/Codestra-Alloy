# Codestra Alloy Production Server and Native API Contract

## Authority

- Repository: `appolon1908-hue/Codestra-Alloy`
- Role: business-scoped host and service log collection agent
- Canonical hostname: `allo.codestra.media`
- Central production host: `37.27.128.39`
- Core application host `65.109.65.169`: separate agent-only extension after central certification
- Status: `SOURCE_CONTRACT_PREPARED_NOT_DEPLOYED`

Alloy owns explicit log-root collection, approved journal collection, redaction, WAL/backpressure behavior, Loki forwarding, source-bound image construction, release evidence, and rollback. OpenTelemetry owns application OTLP; Node Exporter owns host metrics; cAdvisor owns container metrics; Prometheus owns metric/SLO/alert evaluation.

## Native API surface

| Method | Path | Purpose | Boundary |
|---|---|---|---|
| `GET` | `/-/ready` | readiness | private/read-only |
| `GET` | `/metrics` | Alloy self-metrics | private Prometheus scrape |

Alloy does not expose a business API. Unexpected `404` on required routes, unexpected `5xx`, a public native port, or an unsupported journal stub blocks production.

## Collection and security boundary

- Use explicit business-scoped log roots only.
- Never mount the Docker socket or the global Docker container directory.
- The journal-capable executable must be built from the verified locked source with CGO and the approved journal build tag.
- `codestra_business` comes from deployment configuration; callers cannot override it.
- Redact string, numeric, boolean, and null sensitive values; reject nested sensitive arrays/objects when they cannot be safely sanitized.
- Loki forwarding requires mTLS, CA verification, tenant binding, bounded retry, WAL recovery, and queue/backpressure evidence.
- No host, container, OTLP, business-write, communications, identity, secrets, or financial authority is implied.

## Production gates

```text
PROTECTED_PRODUCTION_SHA=PASS
OFFICIAL_SOURCE_TREE=PASS
SANITIZED_IMPORT_TREE=PASS
SOURCE_BOUND_EXECUTABLE=PASS
JOURNAL_CAPABLE_BUILD=PASS
REDACTION_FIXTURES=PASS
EXPLICIT_LOG_ROOTS=PASS
DOCKER_SOCKET_MOUNTED=NO
IMMUTABLE_IMAGE_DIGEST=PASS
IMAGE_SIGNATURE=PASS
SBOM=PASS
PROVENANCE=PASS
SECRET_SCAN=PASS
ROLLBACK_MANIFEST=PASS
```

## Runtime certification

```text
GET_/-/ready=PASS
GET_/metrics=PASS
JOURNAL_SUPPORT=PASS
SERVICE_FILE_LOGS=PASS
EXPLICIT_CONTAINER_JSON_LOGS=PASS
MTLS_LOKI_WRITE=PASS
LOKI_TENANT_BINDING=PASS
WRONG_BUSINESS_DENIED=PASS
REDACTION_FIXTURES=PASS
WAL_RESTART_RECOVERY=PASS
QUEUE_BACKPRESSURE=PASS
UNEXPECTED_404=0
UNEXPECTED_5XX=0
SOURCE_RUNTIME_DRIFT=0
```

Use synthetic logs only. Central-host certification must finish before a separate reviewed agent installation on `65.109.65.169`.

## Repository-first remediation

Stop the affected wave when a runtime defect appears. Preserve the old healthy agent, fix source/configuration here, add regression tests, commit and push, obtain exact-head CI/review, merge normally, rebuild/sign, update the BOM, and retry. Do not patch the live agent and leave GitHub behind.

## Safety

This document does not deploy Alloy or enable forwarding. SSH changes, business writes, communications delivery, provider effects, lending, payments, and trading remain disabled.