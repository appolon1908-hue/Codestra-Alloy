#!/usr/bin/env python3
"""Fail-closed validation for the Codestra Alloy intake monitoring contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "codestra" / "intake-monitoring.v1.json"
CONFIG = ROOT / "codestra" / "config.alloy"

REQUIRED_EVENTS = {
    "codestra.events.lead_submitted",
    "codestra.events.survey_response_submitted",
}
REQUIRED_SAFE_DIMENSIONS = {
    "codestra_business",
    "application",
    "service",
    "environment",
    "server",
    "region",
    "deployment",
    "channel",
    "form_kind",
    "survey_kind",
    "result",
    "reason",
    "delivery_target",
    "anonymous",
}
REQUIRED_FORBIDDEN = {
    "tenant_id",
    "site_id",
    "campaign_id",
    "form_id",
    "survey_id",
    "question_id",
    "customer_id",
    "contact_id",
    "lead_id",
    "response_id",
    "account_id",
    "user_id",
    "email",
    "phone",
    "name",
    "address",
    "message",
    "transcript",
    "answers",
    "custom_fields",
    "consent_text",
    "request_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "idempotency_key",
    "raw_url",
    "query_string",
    "referrer",
    "landing_page",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}
REQUIRED_SOURCES = {
    "middleware-intake",
    "intake-workers",
    "odoo-intake-adapter",
}
REQUIRED_ACTIVATION = {
    "runtimeApplied",
    "productionTargetsEnabled",
    "liveBusinessWritesEnabledByThisContract",
}
CREDENTIAL_KEYS = {
    "authorization",
    "bearer_token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "client_secret",
    "access_token",
    "refresh_token",
    "session_token",
    "private_key",
    "root_token",
    "cookie",
    "set_cookie",
}
PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    flags=re.IGNORECASE,
)


def fail(message: str) -> None:
    raise SystemExit(message)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def scan_credential_values(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = normalize_key(str(key))
            child_path = f"{path}.{key}"
            if normalized in CREDENTIAL_KEYS and child not in (None, "", False, [], {}):
                fail(f"credential-shaped value found in intake contract at {child_path}")
            scan_credential_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_credential_values(child, f"{path}[{index}]")
    elif isinstance(value, str) and PEM_PRIVATE_KEY.search(value):
        fail(f"PEM private-key material found in intake contract at {path}")


def main() -> None:
    try:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid intake contract JSON: {exc}")

    if data.get("schemaVersion") != "1.0":
        fail("intake contract schemaVersion must be 1.0")
    if data.get("status") != "CONTRACT_PREPARED_NOT_DEPLOYED":
        fail("intake contract must remain source-only")
    if data.get("domain") != "unified-intake" or data.get("component") != "alloy":
        fail("intake contract identity mismatch")
    if set(data.get("events", [])) != REQUIRED_EVENTS:
        fail("intake event catalogue mismatch")

    safe = set(data.get("safeDimensions", []))
    forbidden = set(data.get("forbiddenLabelsOrPayloads", []))
    if safe != REQUIRED_SAFE_DIMENSIONS:
        fail("Alloy intake safe dimensions do not match the corporate contract")
    if forbidden != REQUIRED_FORBIDDEN:
        fail("Alloy intake forbidden payload catalogue mismatch")
    if safe & forbidden:
        fail("an intake field cannot be both safe and forbidden")

    privacy = data.get("privacyRules", {})
    required_privacy = {
        "rawFormAnswersInTelemetry",
        "rawSurveyAnswersInTelemetry",
        "contactDataInMetricLabels",
        "customerOrPersonDataInLogLabels",
        "anonymousSurveyMayCarryContactOrLeadId",
        "browserReceivesObservabilityCredentials",
    }
    if set(privacy) != required_privacy:
        fail("Alloy intake privacy-rule catalogue mismatch")
    for field in required_privacy:
        if privacy.get(field) is not False:
            fail(f"privacy boundary must remain false: {field}")

    activation = data.get("activation", {})
    if set(activation) != REQUIRED_ACTIVATION:
        fail("Alloy intake activation-gate catalogue mismatch")
    if any(value is not False for value in activation.values()):
        fail("all intake activation gates must remain false")

    features = data.get("features", {})
    if set(features.get("acceptedSources", [])) != REQUIRED_SOURCES:
        fail("Alloy intake source allowlist mismatch")
    if features.get("eventFamily") != "intake":
        fail("Alloy intake event family mismatch")
    for field in (
        "dropPrivateKeyMaterial",
        "replaceFormAndSurveyContent",
        "dropSensitivePayloadLines",
    ):
        if features.get(field) is not True:
            fail(f"required intake privacy feature is disabled: {field}")
    if features.get("crossBusinessCollection") is not False:
        fail("cross-business intake collection must remain denied")

    config = CONFIG.read_text(encoding="utf-8")
    normalized = config.lower().replace(r"\.", ".")
    for source in REQUIRED_SOURCES:
        if source not in normalized:
            fail(f"Alloy intake selector omits accepted source: {source}")
    if normalized.count('drop_counter_reason = "intake_sensitive_payload"') < 2:
        fail("structured and unstructured intake payload drops are both required")
    for field in REQUIRED_FORBIDDEN:
        if field not in normalized:
            fail(f"Alloy intake redaction policy omits forbidden field: {field}")
    for fragment in (
        "-----begin (?:openssh |rsa |ec |dsa )?private key-----",
        "-----end (?:openssh |rsa |ec |dsa )?private key-----",
        'drop_counter_reason = "pem_or_base64_material"',
    ):
        if fragment not in normalized:
            fail(f"Alloy private-key suppression omits: {fragment}")

    scan_credential_values(data)
    serialized = CONTRACT.read_text(encoding="utf-8")
    if PEM_PRIVATE_KEY.search(serialized):
        fail("PEM private-key material found in intake contract")

    print("Codestra Alloy intake monitoring validation PASS")


if __name__ == "__main__":
    main()
