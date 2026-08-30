#!/usr/bin/env python3
"""Fail-closed validation for the Codestra Alloy intake monitoring contract."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "codestra" / "intake-monitoring.v1.json"

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
    "campaign_id",
    "form_id",
    "survey_id",
    "question_id",
    "customer_id",
    "contact_id",
    "lead_id",
    "response_id",
    "email",
    "phone",
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
}
REQUIRED_SOURCES = {
    "middleware-intake",
    "intake-workers",
    "odoo-intake-adapter",
}


def fail(message: str) -> None:
    raise SystemExit(message)


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
    if not REQUIRED_FORBIDDEN.issubset(forbidden):
        fail("Alloy intake contract omits protected fields")
    if safe & forbidden:
        fail("an intake field cannot be both safe and forbidden")

    privacy = data.get("privacyRules", {})
    for field in (
        "rawFormAnswersInTelemetry",
        "rawSurveyAnswersInTelemetry",
        "contactDataInMetricLabels",
        "customerOrPersonDataInLogLabels",
        "anonymousSurveyMayCarryContactOrLeadId",
        "browserReceivesObservabilityCredentials",
    ):
        if privacy.get(field) is not False:
            fail(f"privacy boundary must remain false: {field}")

    activation = data.get("activation", {})
    if not activation or any(value is not False for value in activation.values()):
        fail("all intake activation gates must remain false")

    features = data.get("features", {})
    if set(features.get("acceptedSources", [])) != REQUIRED_SOURCES:
        fail("Alloy intake source allowlist mismatch")
    if features.get("eventFamily") != "intake":
        fail("Alloy intake event family mismatch")
    if features.get("dropPrivateKeyMaterial") is not True:
        fail("private-key material must be dropped")
    if features.get("replaceFormAndSurveyContent") is not True:
        fail("form and survey content must be replaced before Loki write")
    if features.get("crossBusinessCollection") is not False:
        fail("cross-business intake collection must remain denied")

    serialized = CONTRACT.read_text(encoding="utf-8").lower()
    for secret_shape in ("-----begin private key-----", "bearer ", "password=", "api_key="):
        if secret_shape in serialized:
            fail("secret-shaped content found in intake contract")

    print("Codestra Alloy intake monitoring validation PASS")


if __name__ == "__main__":
    main()
