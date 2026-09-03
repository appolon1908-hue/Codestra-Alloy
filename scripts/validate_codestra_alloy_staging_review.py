#!/usr/bin/env python3
"""Fail-closed validation for Alloy staging-review remediations."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "CODESTRA_UPSTREAM_LOCK.json"
CONFIG_PATH = ROOT / "codestra" / "config.alloy"
PROFILE_PATH = ROOT / "codestra" / "enterprise-profile.v1.json"
IMAGE_CONTRACT_PATH = ROOT / "codestra" / "source-image-contract.v1.json"
DOCKERFILE_PATH = ROOT / "codestra" / "deploy" / "Dockerfile"
SYNC_PATH = ROOT / ".github" / "workflows" / "upstream-source-sync.yml"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SANITIZED_PATH = "integration-tests/docker/tests/loki-azure-event-hubs/certs"
SANITIZATION_REASON = (
    "Official upstream integration-test certificate and private-key fixtures remain "
    "excluded from the Codestra parent repository and GitHub push-protection scope. "
    "No runtime or product source is modified."
)
BUILDER_IMAGE = "grafana/alloy-build-image:v0.1.35"
BUILDER_DIGEST = "9fa2a341b53503ce42cf9900c401d689a68ea67cdec6a20f53d72e3665fb8dc6"

IMPLEMENTED_COLLECTION = [
    "service_file_logs",
    "explicit_container_json_logs",
    "approved_systemd_journal_logs",
    "alloy_self_metrics",
]
EXTERNAL_AUTHORITIES = {
    "application_otlp": "Codestra-Telemetry",
    "host_metrics": "Codestra-Node-Exporter",
    "container_metrics": "Codestra-cAdvisor",
    "metrics_storage_slo_and_alert_evaluation": "Codestra-Prometheus",
}

SENSITIVE_KEYS = (
    r"authorization|proxy_authorization|cookie|set-cookie|password|passwd|"
    r"api[_-]?key|client_secret|access_token|refresh_token|session_token|"
    r"private_key|database_url|dsn|broker(?:_|\.)(?:credential|signing_key)|"
    r"exchange(?:_|\.)(?:api_key|secret)|tenant_id|tenant_name|organization_id|"
    r"organization_name|customer_id|customer_name|account_id|user_id|user_name|"
    r"email|phone|message_id|order_id|workflow_id|execution_id|request\.body|"
    r"response\.body|http\.request\.body|http\.response\.body|db\.statement"
)
SCALAR_EXPRESSION = (
    rf'(?i)("(?:{SENSITIVE_KEYS})"\s*:\s*)'
    r'(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null)'
    r'(\s*[,}])'
)
COMPLEX_EXPRESSION = rf'(?i)"(?:{SENSITIVE_KEYS})"\s*:\s*[\[{{]'


def fail(message: str) -> None:
    print(f"ALLOY_STAGING_REVIEW_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode:
        fail(f"git {' '.join(args)} failed: {completed.stdout.strip()}")
    return completed.stdout.strip()


def require_sha40(value: Any, label: str) -> str:
    text = str(value or "")
    if not SHA40.fullmatch(text):
        fail(f"{label} must be a full lowercase Git SHA")
    return text


def validate_upstream_tree() -> dict[str, Any]:
    lock = load_json(LOCK_PATH)
    expected_static = {
        "schema_version": "1.1",
        "upstream_clone_url": "https://github.com/grafana/alloy.git",
        "upstream_ref": "main",
        "import_path": "upstream",
        "source_tree_verification_required": True,
        "deployment_enabled": False,
        "secret_material_allowed_in_git": False,
    }
    for key, expected_value in expected_static.items():
        if lock.get(key) != expected_value:
            fail(f"upstream lock mismatch for {key}")

    require_sha40(lock.get("upstream_commit"), "upstream_commit")
    require_sha40(lock.get("official_tree_sha"), "official_tree_sha")
    imported_tree = require_sha40(lock.get("imported_tree_sha"), "imported_tree_sha")

    if lock.get("sanitization") != {
        "mode": "remove-explicit-upstream-test-fixtures",
        "removed_paths": [SANITIZED_PATH],
        "reason": SANITIZATION_REASON,
    }:
        fail("upstream sanitization must contain the single approved fixture path")
    if git_output("rev-parse", "HEAD:upstream") != imported_tree:
        fail("vendored upstream tree does not match imported_tree_sha")
    if (ROOT / "upstream" / SANITIZED_PATH).exists():
        fail("excluded upstream certificate fixture path is present")

    sync = read_text(SYNC_PATH)
    for fragment in (
        "OFFICIAL_TREE_SHA=",
        "IMPORTED_TREE_SHA=",
        "git -C .codestra-upstream-src write-tree",
        "remove-explicit-upstream-test-fixtures",
        SANITIZED_PATH,
        "Verify imported tree before",
        "codestra/source-image-contract.v1.json",
        "'upstreamCommit':os.environ['UPSTREAM_SHA']",
        "'officialTreeSha':os.environ['OFFICIAL_TREE_SHA']",
        "'importedTreeSha':os.environ['IMPORTED_TREE_SHA']",
        "python3 scripts/validate_codestra_alloy_staging_review.py",
    ):
        if fragment not in sync:
            fail(f"upstream sync omits provenance or contract regeneration: {fragment}")
    return lock


def validate_redaction() -> None:
    config = read_text(CONFIG_PATH)
    expressions = re.findall(r"expression\s*=\s*`([^`]*)`", config)
    if SCALAR_EXPRESSION not in expressions:
        fail("non-string sensitive JSON replacement is missing")
    if COMPLEX_EXPRESSION not in expressions:
        fail("complex sensitive JSON rejection is missing")
    if 'drop_counter_reason = "complex_sensitive_json_value"' not in config:
        fail("complex sensitive JSON drop reason is missing")
    if 'replace    = "$1\\\"[REDACTED]\\\"$2"' not in config:
        fail("scalar sensitive JSON replacement must preserve valid JSON quoting")

    scalar = re.compile(SCALAR_EXPRESSION)
    fixtures = {
        '{"customer_id":12345}': '{"customer_id":"[REDACTED]"}',
        '{"account_id":null}': '{"account_id":"[REDACTED]"}',
        '{"user_id":false,"result":"denied"}': '{"user_id":"[REDACTED]","result":"denied"}',
        '{"order_id":-1.25e3}': '{"order_id":"[REDACTED]"}',
    }
    for source, expected in fixtures.items():
        actual = scalar.sub(r'\1"[REDACTED]"\2', source)
        if actual != expected:
            fail(f"scalar redaction fixture failed: {source} -> {actual}")

    complex_value = re.compile(COMPLEX_EXPRESSION)
    for source in (
        '{"customer_id":[12345]}',
        '{"account_id":{"raw":12345}}',
        '{"authorization":{"token":"secret"}}',
    ):
        if complex_value.search(source) is None:
            fail(f"complex sensitive JSON fixture is not rejected: {source}")


def validate_enterprise_claims() -> None:
    profile = load_json(PROFILE_PATH)
    if profile.get("role") != "business-scoped-host-and-service-log-collection-agent":
        fail("enterprise role overclaims Alloy authority")
    if profile.get("collect") != IMPLEMENTED_COLLECTION:
        fail("enterprise collect catalogue must contain implemented signals only")
    if profile.get("destinations") != ["loki"]:
        fail("enterprise destination must remain Loki-only")
    if profile.get("externallyOwnedCapabilities") != EXTERNAL_AUTHORITIES:
        fail("external telemetry ownership catalogue mismatch")

    features = profile.get("features")
    if not isinstance(features, dict):
        fail("enterprise features must be an object")
    required_true = {
        "reusableServerProfiles",
        "logLabelNormalization",
        "piiAndSecretRedaction",
        "localWalBuffering",
        "backpressureVisibility",
        "selfMonitoring",
        "privateLokiWrite",
        "deploymentMetadata",
    }
    required_false = {
        "prometheusMetricCollection",
        "applicationOtlpReceiver",
        "hostMetricCollection",
        "containerMetricCollection",
    }
    if any(features.get(key) is not True for key in required_true):
        fail("an implemented Alloy enterprise feature is disabled")
    if any(features.get(key) is not False for key in required_false):
        fail("an externally owned capability is advertised as implemented")
    if set(features) != required_true | required_false:
        fail("unexpected Alloy enterprise feature claim")


def validate_source_bound_image(lock: dict[str, Any]) -> None:
    contract = load_json(IMAGE_CONTRACT_PATH)
    if contract.get("schemaVersion") != "1.0":
        fail("source image contract schema mismatch")
    if contract.get("status") != "SOURCE_BOUND_BUILD_CONTRACT_PREPARED_NOT_RELEASED":
        fail("source image contract must remain not released")
    if contract.get("sourceAuthority") != {
        "repository": "https://github.com/grafana/alloy.git",
        "upstreamCommit": lock["upstream_commit"],
        "officialTreeSha": lock["official_tree_sha"],
        "importedTreeSha": lock["imported_tree_sha"],
        "sanitizedPaths": [SANITIZED_PATH],
    }:
        fail("source image authority does not match upstream lock")
    if contract.get("builder") != {
        "image": BUILDER_IMAGE,
        "digest": BUILDER_DIGEST,
        "cgoToolchainRequired": True,
        "systemdDevelopmentFilesRequired": True,
    }:
        fail("source builder must remain the approved journal-capable image")
    if contract.get("runtimeExecutable") != {
        "buildContext": "upstream/collector",
        "outputPath": "/bin/alloy",
        "builtFromImportedTree": True,
        "cgoEnabled": True,
        "buildTags": ["promtail_journal_enabled"],
        "systemdJournalImplementation": "enabled",
        "readOnlyProxyPath": "/alloy-readonly-proxy",
        "readOnlyProxyBuiltFromRepositorySource": True,
        "inheritedBaseImageExecutableAllowed": False,
        "embeddedSourceLockPath": "/usr/share/codestra/CODESTRA_UPSTREAM_LOCK.json",
    }:
        fail("runtime executable is not journal-capable or source-bound")
    if contract.get("runtimeBaseImage") != {
        "role": "runtime-substrate-only",
        "digestRequired": True,
        "sourceAuthority": False,
    }:
        fail("runtime base image may not become source authority")

    final_image = contract.get("finalImage")
    if not isinstance(final_image, dict) or final_image.get("digest") is not None:
        fail("final image digest may not be claimed before verified build")
    for key in (
        "digestMustBeRecordedBeforeDeployment",
        "provenanceMustReferenceImportedTree",
        "sbomRequired",
        "signatureRequired",
    ):
        if final_image.get(key) is not True:
            fail(f"final image release gate must be true: {key}")
    activation = contract.get("activation")
    if not isinstance(activation, dict) or not activation:
        fail("source image activation map is missing")
    if any(value is not False for value in activation.values()):
        fail("source image activation must remain false")

    dockerfile = read_text(DOCKERFILE_PATH)
    required_fragments = (
        "FROM ${GO_BUILDER_IMAGE} AS alloy-builder",
        "COPY upstream /src/upstream",
        "WORKDIR /src/upstream/collector",
        "CGO_ENABLED=1 GOOS=linux go build",
        "-buildvcs=false",
        "-tags='promtail_journal_enabled'",
        "-o /out/alloy",
        "FROM ${ALLOY_BASE_IMAGE}",
        "COPY --from=alloy-builder --chown=10001:10001 --chmod=0555 /out/alloy /bin/alloy",
        "COPY --chown=10001:10001 --chmod=0444 CODESTRA_UPSTREAM_LOCK.json /usr/share/codestra/CODESTRA_UPSTREAM_LOCK.json",
        'LABEL codestra.runtime.base-role="runtime-substrate-only"',
        'LABEL codestra.feature.systemd-journal="promtail_journal_enabled"',
    )
    for fragment in required_fragments:
        if fragment not in dockerfile:
            fail(f"Dockerfile source binding is missing: {fragment}")
    base_index = dockerfile.find("FROM ${ALLOY_BASE_IMAGE}")
    copy_index = dockerfile.find(
        "COPY --from=alloy-builder --chown=10001:10001 --chmod=0555 /out/alloy /bin/alloy"
    )
    if base_index < 0 or copy_index <= base_index:
        fail("source-built Alloy binary must overwrite the runtime-base executable")


def main() -> None:
    lock = validate_upstream_tree()
    validate_redaction()
    validate_enterprise_claims()
    validate_source_bound_image(lock)
    print("CODESTRA_ALLOY_STAGING_REVIEW_VALIDATION_PASS=1")


if __name__ == "__main__":
    main()
