#!/usr/bin/env python3
"""Fail-closed validation for the Codestra Alloy corporate overlay."""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODESTRA = ROOT / "codestra"
RUNTIME = CODESTRA / "runtime.v1.json"
CONFIG = CODESTRA / "config.alloy"
COMPOSE = CODESTRA / "deploy" / "compose.candidate.yaml"
DOCKERFILE = CODESTRA / "deploy" / "Dockerfile"
HEALTHCHECK = CODESTRA / "deploy" / "healthcheck.go"
ENV_EXAMPLE = CODESTRA / "deploy" / "runtime.env.example"
OPERATING_MODEL = CODESTRA / "docs" / "OPERATING-MODEL.md"
RUNTIME_FEATURES = CODESTRA / "docs" / "RUNTIME-FEATURES.md"

BUSINESSES = {
    "platform",
    "codestra",
    "moneybee",
    "beyvra",
    "breero",
    "larim-a",
    "transportation",
    "booked4seasons",
    "social",
    "klyrow",
    "telnexa",
    "kyqra",
    "restaurant",
    "provisioning",
}
REQUIRED_LABELS = {
    "codestra_business",
    "application",
    "service",
    "environment",
    "server",
    "region",
    "deployment",
    "log_source",
}
REQUIRED_FORBIDDEN_LABELS = {
    "tenant_id",
    "customer_id",
    "account_id",
    "user_id",
    "email",
    "phone",
    "request_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "message_id",
    "order_id",
    "path",
    "filename",
    "container_id",
    "image_id",
    "pod_uid",
    "process_pid",
}
FORBIDDEN_CONFIG_FRAGMENTS = (
    "/var/run/docker.sock",
    "/run/docker.sock",
    "/var/lib/docker/containers/*",
    "discovery.docker",
    "loki.source.docker",
    "prometheus.exporter.unix",
    "prometheus.exporter.cadvisor",
    "otelcol.receiver.otlp",
    "insecure_skip_verify = true",
)
REQUIRED_REDACTION_TOKENS = {
    "authorization",
    "cookie",
    "password",
    "api[_-]?key",
    "client_secret",
    "access_token",
    "refresh_token",
    "session_token",
    "private_key",
    "database_url",
    "broker",
    "exchange",
    "tenant_id",
    "customer_id",
    "account_id",
    "user_id",
    "email",
    "phone",
    "request.body",
    "response.body",
    "db.statement",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(path: pathlib.Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(require_file(path))
    except Exception as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(require_file(path))
    except Exception as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def validate_runtime() -> None:
    runtime = load_json(RUNTIME)
    if runtime.get("schemaVersion") != "1.0":
        fail("Alloy runtime schemaVersion must be 1.0")
    if runtime.get("component") != "alloy":
        fail("Alloy runtime component mismatch")
    if runtime.get("canonicalHostname") != "allo.codestra.media":
        fail("canonical Alloy hostname mismatch")
    if runtime.get("exposure") != "internal_private":
        fail("Alloy exposure must remain internal_private")
    if runtime.get("status") != "CONFIG_PREPARED_NOT_DEPLOYED":
        fail("Alloy runtime must remain CONFIG_PREPARED_NOT_DEPLOYED")
    if set(runtime.get("businessScope", [])) != BUSINESSES:
        fail("Alloy runtime must exactly represent the approved business catalogue")

    model = runtime.get("instanceModel", {})
    if model.get("scope") != "one_business_one_server_boundary":
        fail("Alloy must remain one business per server-agent boundary")
    if model.get("callerSuppliedBusinessIdentityTrusted") is not False:
        fail("caller-supplied business identity may not be trusted")
    if model.get("crossBusinessCollectionDefault") != "deny":
        fail("cross-business collection must default to deny")
    if model.get("sharedServerRequiresSeparateLogRoots") is not True:
        fail("shared servers must require separate business log roots")

    collection = runtime.get("collection", {})
    expected_false = {
        "dockerSocket",
        "globalDockerContainerDirectory",
        "privilegedMode",
        "hostNetwork",
        "hostMetrics",
        "containerMetrics",
        "applicationOtlpGateway",
    }
    for field in expected_false:
        if collection.get(field) is not False:
            fail(f"Alloy collection boundary must remain false: {field}")
    if collection.get("selfMetrics") is not True:
        fail("Alloy self-metrics must be enabled")

    if set(runtime.get("requiredStreamLabels", [])) != REQUIRED_LABELS:
        fail("Alloy stream labels do not match the corporate log contract")
    if not REQUIRED_FORBIDDEN_LABELS.issubset(
        set(runtime.get("forbiddenStreamLabels", []))
    ):
        fail("Alloy runtime does not forbid all unsafe stream labels")

    delivery = runtime.get("delivery", {})
    for field in ("mutualTls", "certificateVerification", "walEnabled", "boundedBackoff"):
        if delivery.get(field) is not True:
            fail(f"Alloy delivery feature must be enabled: {field}")
    if delivery.get("lokiTenantIdSource") != "CODESTRA_BUSINESS":
        fail("Loki tenant ID must come from the deployment-controlled business")

    hardening = runtime.get("runtime", {})
    expected_runtime = {
        "uid": 10001,
        "gid": 10001,
        "readOnlyRootFilesystem": True,
        "dropAllCapabilities": True,
        "noNewPrivileges": True,
        "nativeHostPortPublished": False,
        "dockerSocketMounted": False,
        "immutableImageRequired": True,
    }
    for field, expected in expected_runtime.items():
        if hardening.get(field) != expected:
            fail(f"Alloy runtime hardening mismatch for {field}")

    activation = runtime.get("activation", {})
    if not activation or any(value is not False for value in activation.values()):
        fail("all Alloy activation gates must remain false before evidence exists")


def validate_alloy_config() -> None:
    text = require_file(CONFIG)
    for fragment in FORBIDDEN_CONFIG_FRAGMENTS:
        if fragment in text:
            fail(f"Alloy config contains forbidden authority or access: {fragment}")

    required_fragments = (
        'format = "json"',
        'local.file_match "service_files"',
        'local.file_match "docker_files"',
        'loki.source.file "service_files"',
        'loki.source.file "docker_files"',
        'loki.source.journal "system"',
        '/var/log/codestra/*/*/*.log',
        '/var/log/codestra/*/*/docker/*-json.log',
        'path       = "/run/log/journal"',
        'sys.env("CODESTRA_BUSINESS")',
        'sys.env("CODESTRA_ENVIRONMENT")',
        'sys.env("CODESTRA_REGION")',
        'sys.env("CODESTRA_SERVER")',
        'sys.env("CODESTRA_ALLOY_DEPLOYMENT_ID")',
        'stage.docker {}',
        'stage.label_drop',
        'values = ["filename"]',
        'loki.process "redact"',
        'drop_counter_reason = "private_key_material"',
        'loki.write "codestra"',
        'tenant_id      = sys.env("CODESTRA_BUSINESS")',
        'ca_file              = "/run/secrets/loki_ca"',
        'cert_file            = "/run/secrets/alloy_client_cert"',
        'key_file             = "/run/secrets/alloy_client_key"',
        'insecure_skip_verify = false',
        'wal {',
        'enabled            = true',
        'max_retries = 10',
    )
    for fragment in required_fragments:
        if fragment not in text:
            fail(f"Alloy config is missing required corporate behavior: {fragment}")

    for label in REQUIRED_LABELS:
        if label not in text:
            fail(f"Alloy config does not assign required stream label: {label}")

    lowered = text.lower()
    for token in REQUIRED_REDACTION_TOKENS:
        if token.lower() not in lowered:
            fail(f"Alloy redaction policy omits token class: {token}")

    # Only controlled application/service directory names may become dynamic labels.
    stage_label_blocks = re.findall(
        r"stage\.labels\s*\{(.*?)\}", text, flags=re.DOTALL
    )
    if len(stage_label_blocks) != 2:
        fail("Alloy must have exactly two dynamic label stages")
    for block in stage_label_blocks:
        label_names = set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", block, re.MULTILINE))
        if label_names != {"application", "service"}:
            fail(f"unsafe dynamic Alloy labels: {sorted(label_names)}")

    if re.search(r"(?m)^\s*(trace_id|correlation_id|request_id|customer_id|user_id|email|phone)\s*=", text):
        fail("high-cardinality or personal fields may not be assigned as stream labels")


def validate_compose() -> None:
    compose = load_yaml(COMPOSE)
    services = compose.get("services", {})
    if set(services) != {"alloy"}:
        fail("Alloy Compose candidate must define exactly one Alloy service")
    service = services["alloy"]
    if service.get("user") != "10001:10001":
        fail("Alloy must run as UID/GID 10001")
    if service.get("read_only") is not True:
        fail("Alloy root filesystem must be read-only")
    if service.get("privileged") is True or service.get("network_mode") == "host":
        fail("Alloy may not use privileged or host-network mode")
    if service.get("pid") == "host":
        fail("Alloy may not use the host PID namespace")
    if "ALL" not in service.get("cap_drop", []):
        fail("Alloy must drop all Linux capabilities")
    if "no-new-privileges:true" not in service.get("security_opt", []):
        fail("Alloy must set no-new-privileges")
    if service.get("ports"):
        fail("Alloy may not publish a host port")
    if set(map(str, service.get("expose", []))) != {"12345"}:
        fail("Alloy must expose only its private self-metrics/readiness port")
    if set(service.get("networks", [])) != {
        "codestra-business-logs",
        "codestra-observability",
    }:
        fail("Alloy must attach only to its business-log and observability networks")
    if set(service.get("secrets", [])) != {
        "loki_ca",
        "alloy_client_cert",
        "alloy_client_key",
    }:
        fail("Alloy Loki mTLS secret-file contract is incomplete")
    if service.get("healthcheck", {}).get("test") != ["CMD", "/alloy-healthcheck"]:
        fail("Alloy must use the native readiness probe")

    volumes = service.get("volumes", [])
    if "alloy-data:/var/lib/alloy" not in [str(item) for item in volumes]:
        fail("Alloy durable storage volume is missing")
    bind_targets = {
        item.get("target")
        for item in volumes
        if isinstance(item, dict) and item.get("type") == "bind"
    }
    if bind_targets != {"/var/log/codestra", "/run/log/journal", "/etc/machine-id"}:
        fail("Alloy host bind targets do not match the approved allowlist")
    for item in volumes:
        if isinstance(item, dict) and item.get("type") == "bind":
            if item.get("read_only") is not True:
                fail(f"Alloy host bind must be read-only: {item.get('target')}")
            if item.get("bind", {}).get("create_host_path") is not False:
                fail(f"Alloy may not auto-create host path: {item.get('target')}")

    image = str(service.get("image", ""))
    if "${CODESTRA_ALLOY_IMAGE:" not in image or "sha256" not in image:
        fail("Alloy final image must require an immutable digest")
    build_args = service.get("build", {}).get("args", {})
    if set(build_args) != {"GO_BUILDER_IMAGE", "ALLOY_BASE_IMAGE"}:
        fail("Alloy build must pin builder and upstream images")
    limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
    for field in ("cpus", "memory", "pids"):
        if field not in limits:
            fail(f"Alloy runtime is missing resource limit {field}")

    serialized = COMPOSE.read_text(encoding="utf-8")
    for forbidden in (
        "/var/run/docker.sock",
        "/run/docker.sock",
        "/var/lib/docker/containers",
        ":latest",
        "privileged: true",
        "network_mode: host",
        "pid: host",
        "0.0.0.0:12345",
    ):
        if forbidden in serialized:
            fail(f"Alloy runtime contains forbidden content: {forbidden}")


def validate_packaging_and_docs() -> None:
    dockerfile = require_file(DOCKERFILE)
    for fragment in (
        "ARG GO_BUILDER_IMAGE",
        "ARG ALLOY_BASE_IMAGE",
        "CGO_ENABLED=0",
        "-trimpath",
        "/alloy-healthcheck",
        "/etc/alloy/config.alloy",
        "USER 10001:10001",
    ):
        if fragment not in dockerfile:
            fail(f"Alloy Dockerfile is missing {fragment}")
    if ":latest" in dockerfile:
        fail("Alloy Dockerfile may not use latest tags")

    healthcheck = require_file(HEALTHCHECK)
    if "http://127.0.0.1:12345/-/ready" not in healthcheck:
        fail("Alloy health probe must use the local readiness endpoint")
    if "os/exec" in healthcheck or "exec.Command" in healthcheck:
        fail("Alloy health probe may not invoke a shell or subprocess")

    env_text = require_file(ENV_EXAMPLE)
    for fragment in (
        "CODESTRA_BUSINESS=platform",
        "CODESTRA_ALLOY_DEPLOYMENT_ID=",
        "GO_BUILDER_IMAGE=",
        "ALLOY_BASE_IMAGE=",
        "CODESTRA_ALLOY_IMAGE=",
        "ALLOY_LOG_SOURCE_PATH=",
        "ALLOY_JOURNAL_SOURCE_PATH=",
        "CODESTRA_BUSINESS_LOG_NETWORK=",
        "ALLOY_LOKI_CA_SECRET_NAME=",
        "ALLOY_CLIENT_CERT_SECRET_NAME=",
        "ALLOY_CLIENT_KEY_SECRET_NAME=",
    ):
        if fragment not in env_text:
            fail(f"Alloy runtime example omits {fragment}")

    require_file(OPERATING_MODEL)
    require_file(RUNTIME_FEATURES)


def validate_secret_safety() -> None:
    dash = chr(45) * 5
    signatures = (
        dash + "BEGIN " + "PRIVATE" + chr(32) + "KEY" + dash,
        dash + "BEGIN " + "OPENSSH" + chr(32) + "PRIVATE" + chr(32) + "KEY" + dash,
        "A" + "K" + "I" + "A",
    )
    for path in CODESTRA.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for signature in signatures:
            if signature in text:
                fail(f"secret-shaped material found in {path.relative_to(ROOT)}")

    config_text = CONFIG.read_text(encoding="utf-8")
    for pattern in (
        r"(?m)^\s*(password|bearer_token|access_token|client_secret)\s*=\s*\"[^\"]+\"",
        r"(?m)^\s*key_file\s*=\s*\"(?!/run/secrets/)",
        r"(?m)^\s*cert_file\s*=\s*\"(?!/run/secrets/)",
        r"(?m)^\s*ca_file\s*=\s*\"(?!/run/secrets/)",
    ):
        if re.search(pattern, config_text):
            fail("Alloy source contains inline or non-secret-file credential material")


def main() -> None:
    validate_runtime()
    validate_alloy_config()
    validate_compose()
    validate_packaging_and_docs()
    validate_secret_safety()
    print("Codestra Alloy corporate agent validation PASS")


if __name__ == "__main__":
    main()
