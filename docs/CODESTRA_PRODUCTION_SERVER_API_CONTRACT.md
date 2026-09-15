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

The upstream Alloy listener registers more than readiness and metrics. Production certification must inventory and constrain the complete enabled surface:

| Method | Path | Purpose | Production boundary |
|---|---|---|---|
| `GET` | `/-/ready` | readiness | private approved health client only |
| `GET` | `/metrics` | Alloy self-metrics | private approved Prometheus client only |
| `GET`, `POST` | `/-/reload` | runtime configuration reload | forbidden from attached network peers; use immutable reviewed redeploy |
| `GET` | `/-/support` | support-bundle access | disabled with the supported flag or denied by a reviewed authenticated proxy/network boundary |

Alloy does not expose a business API. The native listener must not be generally reachable merely because a caller is attached to `codestra-business-logs` or `codestra-observability`. A production deployment that exposes unauthenticated reload or support-bundle access is blocked, even when readiness and metrics pass.

Unexpected `404` on required readiness/metrics routes, unexpected `5xx`, a public native port, an unsupported journal stub, or peer access to reload/support blocks production. A denied administrative route may be absent at the approved proxy, return `401`/`403`, or be unreachable by network policy; a direct successful native response is forbidden.

## Collection and security boundary

- Use explicit business-scoped log roots only.
- Never mount the Docker socket or the global Docker container directory.
- The journal-capable executable must be built from the verified locked source with CGO and the approved journal build tag.
- `codestra_business` comes from deployment configuration; callers cannot override it.
- Redact string, numeric, boolean, and null sensitive values; reject nested sensitive arrays/objects when they cannot be safely sanitized.
- Loki forwarding requires mTLS, CA verification, tenant binding, bounded retry, WAL recovery, and queue/backpressure evidence.
- The production HTTP boundary exposes only approved readiness and self-metric access. HTTP reload is replaced by immutable repository-controlled rollout; support bundles are disabled or privileged and audited.
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
NATIVE_HTTP_ROUTE_INVENTORY=PASS
HTTP_RELOAD_FROM_NETWORK_PEER=DENIED
SUPPORT_BUNDLE_FROM_NETWORK_PEER=DENIED
SUPPORT_BUNDLE_DISABLED_OR_AUTHORIZED_PROXY=PASS
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
GET_OR_POST_/-/reload=DENIED_401_403_ABSENT_AT_PROXY_OR_NETWORK
GET_/-/support=DENIED_401_403_ABSENT_AT_PROXY_OR_NETWORK
DIRECT_NATIVE_RELOAD_SUCCESS=NO
DIRECT_NATIVE_SUPPORT_SUCCESS=NO
NATIVE_HTTP_PEER_SCOPE=APPROVED_HEALTH_AND_PROMETHEUS_ONLY
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

The current candidate must not be promoted to production until the reload/support denial gates are implemented and tested at the actual deployed network boundary. Use synthetic logs only. Central-host certification must finish before a separate reviewed agent installation on `65.109.65.169`.

## Repository-first remediation

Stop the affected wave when a runtime defect appears. Preserve the old healthy agent, fix source/configuration here, add regression tests, commit and push, obtain exact-head CI/review, merge normally, rebuild/sign, update the BOM, and retry. Do not patch the live agent and leave GitHub behind.

## Safety

This document does not deploy Alloy or enable forwarding. SSH changes, business writes, communications delivery, provider effects, lending, payments, and trading remain disabled.