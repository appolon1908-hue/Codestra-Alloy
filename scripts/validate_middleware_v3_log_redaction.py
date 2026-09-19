#!/usr/bin/env python3
"""Fail-closed proof that the Alloy redaction stage removes every credential class Middleware V3 logs could carry.

The stages of ``loki.process "redact"`` in ``codestra/config.alloy`` are parsed in
order (drop, replace, match) and replayed over a corpus of log lines that plant one
credential of every class named by the Lane E contract: Authorization headers,
cookies, JWTs, API keys, passwords, client secrets, OpenBao tokens, database,
SMTP and provider credentials (as JSON keys, key=value pairs, environment dumps and
connection URLs). The proof fails if any planted value survives, if a reference
field that drilldown needs (secret_ref, correlation_id, operation_id) is damaged,
or if the contract in ``codestra/contracts/middleware-v3-telemetry-collection.v1.json``
drifts from the configuration. Alloy compiles the same expressions with RE2; the
patterns are kept inside the RE2/Python common subset (no look-around, no
back-references) so this replay is faithful.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "codestra" / "config.alloy"
CONTRACT = ROOT / "codestra" / "contracts" / "middleware-v3-telemetry-collection.v1.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STAGE_RE = re.compile(r"^\t(stage\.(drop|replace|match))\s*\{", re.MULTILINE)
EXPR_RE = re.compile(r"expression\s*=\s*`([^`]*)`")
REPLACE_RE = re.compile(r'replace\s*=\s*"((?:[^"\\]|\\.)*)"')
SELECTOR_RE = re.compile(r'selector\s*=\s*(?:`([^`]*)`|"((?:[^"\\]|\\.)*)")')
LONGER_THAN_RE = re.compile(r'longer_than\s*=\s*"(\d+)(KiB|MiB|B)?"')
REQUIRED_COMMON_FIELDS = ["service_id", "environment", "deployment_sha", "correlation_id", "operation_id", "trace_id"]
REQUIRED_REDACTION_CLASSES = [
    "authorization_headers", "cookies", "jwt", "api_keys", "passwords", "client_secret",
    "openbao_tokens", "database_credentials", "smtp_credentials", "provider_credentials",
]

# (line, planted secret values that must not survive, values that must survive)
CORPUS: list[tuple[str, list[str], list[str]]] = [
    ('GET /v1/x Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJtaWRkbGV3YXJlIn0.c2lnbmF0dXJlLXNpZ25hdHVyZQ', ["eyJhbGciOiJSUzI1NiJ9", "c2lnbmF0dXJlLXNpZ25hdHVyZQ"], []),
    ('{"level":"info","authorization":"Bearer abc.def.ghi","correlation_id":"corr-42"}', ["abc.def.ghi"], ["corr-42"]),
    ('{"cookie":"session=SESSIONVALUE123; csrf=CSRFVALUE"}', ["SESSIONVALUE123", "CSRFVALUE"], []),
    ('Cookie: session=SESSIONVALUE123; Path=/', ["SESSIONVALUE123"], []),
    ('Set-Cookie: KEYCLOAK_IDENTITY=IDENTITYCOOKIEVALUE; HttpOnly', ["IDENTITYCOOKIEVALUE"], []),
    ('{"smtp_password":"S3cr3tSMTPpass","smtp_user":"mailer"}', ["S3cr3tSMTPpass"], ["mailer"]),
    ('SMTP_PASSWORD=S3cr3tSMTPpass SMTP_HOST=smtp.internal', ["S3cr3tSMTPpass"], ["smtp.internal"]),
    ('smtp://mailer:S3cr3tSMTPpass@smtp.internal:587', ["S3cr3tSMTPpass"], ["smtp.internal"]),
    ('{"x-api-key":"pk_live_PROVIDERKEY1234567890"}', ["pk_live_PROVIDERKEY1234567890"], []),
    ('provider_api_key=sk_live_PROVIDERKEY1234567890 provider=klyrow', ["sk_live_PROVIDERKEY1234567890"], ["klyrow"]),
    ('{"telnexa_api_key":"TELNEXAKEYVALUE","adapter":"telnexa"}', ["TELNEXAKEYVALUE"], ["telnexa"]),
    ('{"api_key":"APIKEYVALUE9876"}', ["APIKEYVALUE9876"], []),
    ('DATABASE_URL=postgres://mw:DbPassw0rd@postgres:5432/middleware', ["DbPassw0rd"], []),  # whole DSN value is redacted
    ('connecting to postgresql://mw:DbPassw0rd@postgres:5432/middleware?sslmode=require', ["DbPassw0rd"], ["postgres:5432"]),
    ('{"db_password":"DbPassw0rd","db_host":"postgres"}', ["DbPassw0rd"], ["postgres"]),
    ('{"postgres_password":"DbPassw0rd"}', ["DbPassw0rd"], []),
    ('REDIS_URL=redis://:RedisPassw0rd@redis:6379/0', ["RedisPassw0rd"], ["redis:6379"]),
    ('{"redis_password":"RedisPassw0rd"}', ["RedisPassw0rd"], []),
    ('amqp://nats:NatsPassw0rd@nats:4222', ["NatsPassw0rd"], ["nats:4222"]),
    ('{"client_secret":"kc-client-secret-value-123","client_id":"middleware-api"}', ["kc-client-secret-value-123"], ["middleware-api"]),
    ('KEYCLOAK_CLIENT_SECRET=kc-client-secret-value-123', ["kc-client-secret-value-123"], []),
    ('{"password":"PlainPassw0rd!"}', ["PlainPassw0rd!"], []),
    ('password=PlainPassw0rd! user=ops', ["PlainPassw0rd!"], ["ops"]),
    ('X-Vault-Token: hvs.CAESIabcdefghijklmnopqrstuvwxyz0123456789ABC', ["hvs.CAESI"], []),
    ('X-OpenBao-Token: hvb.AAAAAQJbatchtokenvalue0123456789abcdefghij', ["hvb.AAAAAQJ"], []),
    ('openbao_token=s.abcdefghijklmnopqrstuvwxyz1234', ["s.abcdefghijklmnopqrstuvwxyz1234"], []),
    ('{"bao_token":"BAOTOKENVALUE123","secret_ref":"codestra/production/middleware/api/database"}', ["BAOTOKENVALUE123"], ["codestra/production/middleware/api/database"]),
    ('{"vault_token":"VAULTTOKENVALUE","lease_id_hash":"sha256:abc"}', ["VAULTTOKENVALUE"], ["sha256:abc"]),
    ('Authorization: Basic dXNlcjpwYXNzd29yZC12YWx1ZQ==', ["dXNlcjpwYXNzd29yZC12YWx1ZQ=="], []),
    ('{"aws_secret_access_key":"AWSSECRETVALUE1234567890"}', ["AWSSECRETVALUE1234567890"], []),
    ('{"webhook_signing_secret":"WEBHOOKSIGNINGVALUE"}', ["WEBHOOKSIGNINGVALUE"], []),
    ('{"private_key":"PRIVATEKEYINLINEVALUE"}', ["PRIVATEKEYINLINEVALUE"], []),
    ('{"credentials":{"user":"a","password":"NESTEDPASSWORD"}}', ["NESTEDPASSWORD"], []),
    ('{"provider_credentials":["PROVIDERCREDVALUE"]}', ["PROVIDERCREDVALUE"], []),
    ('{"access_token":"ACCESSTOKENVALUE","refresh_token":"REFRESHTOKENVALUE","id_token":"IDTOKENVALUE"}', ["ACCESSTOKENVALUE", "REFRESHTOKENVALUE", "IDTOKENVALUE"], []),
    ('operator email ops@codestra.co requested replay operation_id=op-123', ["ops@codestra.co"], ["op-123"]),
    ('{"dsn":"postgres://mw:DbPassw0rd@postgres/mw","operation_id":"op-777","deployment_sha":"22d023a9"}', ["DbPassw0rd"], ["op-777", "22d023a9"]),
    ('Client-Secret: ClientSecretHeaderValue', ["ClientSecretHeaderValue"], []),
    ('-----BEGIN RSA PRIVATE KEY----- MIIEowIBAAKCAQEA -----END RSA PRIVATE KEY-----', ["MIIEowIBAAKCAQEA"], []),
]
# Reference and drilldown fields that the stages must leave untouched.
PRESERVED: list[tuple[str, list[str]]] = [
    ('{"secret_ref":"codestra/production/middleware/api/database","secret_class":"database_credentials","rotation_status":"current","token_type":"bearer"}',
     ["codestra/production/middleware/api/database", "database_credentials", "current", "bearer"]),
    ('{"correlation_id":"corr-1","operation_id":"op-1","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736","deployment_sha":"22d023a9c65b","service_id":"middleware","environment":"production"}',
     ["corr-1", "op-1", "4bf92f3577b34da6a3ce929d0e0e4736", "22d023a9c65b", "middleware", "production"]),
    ('{"token_count":12,"idempotency_key":"am:grp:1","lease_id_hash":"sha256:deadbeef"}', ["12", "am:grp:1", "sha256:deadbeef"]),
]


def fail(message: str) -> None:
    print(f"MIDDLEWARE_V3_LOG_REDACTION_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def block(text: str, start: int) -> str:
    """Return the text of the brace block that opens at ``start`` (index of '{')."""
    depth = 0
    quote: str | None = None  # braces inside `raw` or "quoted" strings are not structure
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in ("`", '"'):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
        index += 1
    fail("unbalanced braces in config.alloy")
    return ""


def parse_stages(text: str) -> list[dict[str, Any]]:
    head = text.find('loki.process "redact"')
    if head < 0:
        fail('loki.process "redact" is missing')
    body = block(text, text.index("{", head))
    stages: list[dict[str, Any]] = []
    for match in STAGE_RE.finditer(body):
        kind = match.group(2)
        inner = block(body, body.index("{", match.start()))
        if kind == "match":
            selector = SELECTOR_RE.search(inner)
            nested = [{"kind": "drop", "expression": e} for e in EXPR_RE.findall(inner)]
            if selector is None:
                fail("stage.match without a selector")
            stages.append({"kind": "match", "selector": selector.group(1) or selector.group(2) or "", "stages": nested})
            continue
        expression = EXPR_RE.search(inner)
        if not expression:
            longer = LONGER_THAN_RE.search(inner)
            if kind == "drop" and longer:
                unit = {"KiB": 1024, "MiB": 1024 * 1024}.get(longer.group(2) or "B", 1)
                stages.append({"kind": "length", "limit": int(longer.group(1)) * unit})
                continue
            fail(f"stage.{kind} without an expression")
        stage: dict[str, Any] = {"kind": kind, "expression": expression.group(1)}
        if kind == "replace":
            replacement = REPLACE_RE.search(inner)
            if not replacement:
                fail("stage.replace without a replacement")
            stage["replace"] = replacement.group(1).encode("utf-8").decode("unicode_escape")
        stages.append(stage)
    if not stages:
        fail("no redaction stages found")
    return stages


def compile_stage(expression: str) -> re.Pattern[str]:
    if re.search(r"\(\?[=!<]|\\[1-9]", expression):
        fail(f"expression leaves the RE2/Python common subset: {expression[:60]}")
    try:
        return re.compile(expression)
    except re.error as exc:
        fail(f"expression does not compile: {expression[:60]}: {exc}")
    return re.compile("")


def to_python_replacement(replacement: str) -> str:
    return re.sub(r"\$(\d+)", r"\\\1", replacement.replace("\\", "\\\\"))


def redact(line: str, stages: list[dict[str, Any]], service: str = "middleware") -> str | None:
    """Return the redacted line or None when a stage drops it."""
    for stage in stages:
        if stage["kind"] == "length":
            if len(line.encode("utf-8")) > stage["limit"]:
                return None
            continue
        if stage["kind"] == "match":
            selector = re.search(r'(?:service|application)\s*=~\s*"([^"]+)"', stage["selector"])
            if selector and not re.fullmatch(selector.group(1), service):
                continue
            for nested in stage["stages"]:
                if compile_stage(nested["expression"]).search(line):
                    return None
            continue
        pattern = compile_stage(stage["expression"])
        if stage["kind"] == "drop":
            if pattern.search(line):
                return None
        else:
            line = pattern.sub(to_python_replacement(stage["replace"]), line)
    return line


def validate_corpus(stages: list[dict[str, Any]]) -> tuple[int, int]:
    leaked: list[str] = []
    damaged: list[str] = []
    dropped = 0
    for line, secrets, kept in CORPUS:
        result = redact(line, stages)
        if result is None:
            dropped += 1
            continue
        for secret in secrets:
            if secret in result:
                leaked.append(f"{secret!r} survived in {result!r}")
        for value in kept:
            if value not in result:
                damaged.append(f"{value!r} was damaged in {result!r}")
    for line, kept in PRESERVED:
        result = redact(line, stages)
        if result is None:
            damaged.append(f"reference line was dropped: {line!r}")
            continue
        for value in kept:
            if value not in result:
                damaged.append(f"{value!r} was damaged in {result!r}")
    if leaked:
        fail("LOG_REDACTION=FAIL " + "; ".join(leaked[:5]))
    if damaged:
        fail("LOG_REDACTION damaged drilldown fields: " + "; ".join(damaged[:5]))
    return len(CORPUS), dropped


def validate_contract(contract: dict[str, Any], text: str) -> None:
    if contract.get("contract_id") != "middleware-v3-telemetry-collection" or contract.get("status") != "PREPARED_DISABLED":
        fail("contract identity or status drift")
    if contract.get("activation_enabled") is not False:
        fail("activation_enabled must be false")
    middleware = contract.get("middleware", {})
    if not SHA40.fullmatch(str(middleware.get("prep_base_sha", ""))):
        fail("middleware.prep_base_sha must be a 40-hex commit")
    if middleware.get("v3_final_sha") != "PENDING" and not SHA40.fullmatch(str(middleware.get("v3_final_sha"))):
        fail("middleware.v3_final_sha must be PENDING or a 40-hex commit")
    fields = contract.get("required_common_fields", {})
    if list(fields) != REQUIRED_COMMON_FIELDS:
        fail(f"required_common_fields must be exactly {REQUIRED_COMMON_FIELDS}")
    for field, placement in fields.items():
        if field in ("service_id", "environment"):
            if placement.get("carried_as") != "stream_label":
                fail(f"{field} must be carried as a stream label")
        elif placement.get("carried_as") != "structured_metadata":
            fail(f"{field} must be structured metadata, never a label")
    classes = contract.get("redaction", {}).get("classes", {})
    missing = [c for c in REQUIRED_REDACTION_CLASSES if c not in classes]
    if missing:
        fail(f"redaction classes missing {missing}")
    for name, spec in classes.items():
        for token in spec.get("config_tokens", []):
            if token not in text:
                fail(f"redaction class {name} references a token absent from config.alloy: {token}")
    metadata = re.findall(r"stage\.structured_metadata\s*\{\s*values\s*=\s*\{(.*?)\}\s*\}", text, flags=re.DOTALL)
    names: set[str] = set()
    for chunk in metadata:
        names |= set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", chunk, flags=re.MULTILINE))
    for field in ("correlation_id", "operation_id", "trace_id", "deployment_sha"):
        if field not in names:
            fail(f"{field} must be assigned as structured metadata for the service stream")
    forbidden = set(contract.get("label_policy", {}).get("never_labels", []))
    for label in ("customer_id", "command_id", "operation_id", "correlation_id", "email", "phone", "tenant_id"):
        if label not in forbidden:
            fail(f"{label} must be declared never-a-label")
    label_blocks = re.findall(r"stage\.labels\s*\{\s*values\s*=\s*\{(.*?)\}\s*\}", text, flags=re.DOTALL)
    for chunk in label_blocks:
        labels = set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", chunk, flags=re.MULTILINE))
        if labels & forbidden:
            fail(f"forbidden labels assigned as stream labels: {sorted(labels & forbidden)}")


def main() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    stages = parse_stages(text)
    total, dropped = validate_corpus(stages)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate_contract(contract, text)
    print(
        f"MIDDLEWARE_V3_LOG_REDACTION=PASS LOG_REDACTION=PASS stages={len(stages)} corpus={total} dropped={dropped} "
        f"prep_base={contract['middleware']['prep_base_sha'][:12]} v3_final={contract['middleware']['v3_final_sha']}"
    )


if __name__ == "__main__":
    main()
