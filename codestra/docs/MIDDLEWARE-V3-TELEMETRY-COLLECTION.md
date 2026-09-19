# Middleware V3 telemetry collection (Lane E preparation)

Status: **PREPARED_DISABLED**. `MIDDLEWARE_PREP_BASE=22d023a9c65b0789a0f7ee6c28548753521a9eff`,
`V3_FINAL_SHA=PENDING`. Alloy collects and transports; it never stores state and never
reaches a business system.

## Contract (`codestra/contracts/middleware-v3-telemetry-collection.v1.json`)

Flow: applications / exporters / journald / OpenBao audit -> Alloy `loki.process`
(labels, structured metadata, redact) -> Loki over mutual TLS. Redaction happens on the
producing host before anything leaves it.

Required common fields and where they travel:

| Field | Carried as |
| --- | --- |
| `service_id` | stream label `service` (bounded) |
| `environment` | stream label `environment` |
| `deployment_sha` | structured metadata (new) |
| `correlation_id` | structured metadata |
| `operation_id` | structured metadata (new) |
| `trace_id` (+ `span_id`) | structured metadata |

Never labels: tenant/customer/account/user ids, e-mail, phone, command/operation/correlation
/trace/request ids, paths, URLs, container/image/pod/process identifiers.

## Redaction hardening in `codestra/config.alloy`

The exact-key stages stay. New stages match credential names by **suffix** so
`smtp_password`, `db_password`, `redis_password`, `provider_api_key`, `x-api-key`,
`bao_token`, `aws_secret_access_key`, `<provider>_client_secret`, `..._credentials`,
`..._dsn` and `..._connection_string` are redacted as JSON values, `key=value` pairs and
environment dumps; objects or arrays under such keys drop the line. Credentials embedded in
connection URLs (`postgres://user:pass@`, `redis://:pass@`, `smtp://`, `amqp://`,
`https://user:pass@`), HTTP `Basic` credentials and legacy `b.` OpenBao batch tokens are
redacted as well. Reference metadata (`secret_ref`, `secret_class`, `lease_id_hash`,
`token_type`, `token_count`, `idempotency_key`) and the drilldown identifiers are preserved.

## Proof

`scripts/validate_middleware_v3_log_redaction.py` parses the `redact` stages in order and
replays a 39-line corpus that plants one credential of every class (Authorization, Cookie,
JWT, API keys, passwords, client_secret, OpenBao tokens, database, SMTP and provider
credentials): **LOG_REDACTION=PASS** means no planted value survives and no drilldown field
is damaged. `tests/test_middleware_v3_log_redaction.py` adds targeted cases. Both run in
`validate-codestra-alloy.yml`; the locked Alloy executable still formats and validates the
configuration in the same workflow.

Redaction is defence in depth: Middleware V3 must never log a resolved secret in the first
place.
