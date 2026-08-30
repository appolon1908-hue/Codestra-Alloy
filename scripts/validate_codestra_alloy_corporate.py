#!/usr/bin/env python3
"""Canonical exact-head validator for the Codestra Alloy corporate overlay.

Alloy's `stage.labels` component stores promoted labels inside a nested `values`
map. Regex policies also escape dots in structured field names such as
`db.statement`. The locked formatter may render an empty block as either `{}` or
`{ }`. This entrypoint preserves every fail-closed policy check while parsing the
actual Alloy syntax correctly.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from types import ModuleType


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "codestra_alloy_policy", "scripts/validate_codestra_alloy.py"
    )
    if spec is None or spec.loader is None:
        fail("unable to load the Alloy policy validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_alloy_config(module: ModuleType) -> None:
    text = module.require_file(module.CONFIG)
    for fragment in module.FORBIDDEN_CONFIG_FRAGMENTS:
        if fragment in text:
            module.fail(f"Alloy config contains forbidden authority or access: {fragment}")

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
        'stage.label_drop',
        'values = ["filename"]',
        'loki.process "redact"',
        'longer_than         = "256KiB"',
        'drop_counter_reason = "line_too_long"',
        'drop_counter_reason = "private_key_material"',
        'loki.write "codestra"',
        'tenant_id           = sys.env("CODESTRA_BUSINESS")',
        'remote_timeout      = "30s"',
        'min_backoff_period  = "500ms"',
        'max_backoff_period  = "5m"',
        'max_backoff_retries = 10',
        'retry_on_http_429   = true',
        'ca_file              = "/run/secrets/loki_ca"',
        'cert_file            = "/run/secrets/alloy_client_cert"',
        'key_file             = "/run/secrets/alloy_client_key"',
        'insecure_skip_verify = false',
        'wal {',
        'enabled            = true',
    )
    for fragment in required_fragments:
        if fragment not in text:
            module.fail(
                f"Alloy config is missing required corporate behavior: {fragment}"
            )

    if "max_line_size" in text or "backoff_config" in text:
        module.fail(
            "Alloy config contains an unsupported source-version line or retry setting"
        )

    if not re.search(r"stage\.docker\s*\{\s*\}", text):
        module.fail("Alloy config is missing the required Docker decoding stage")

    for label in module.REQUIRED_LABELS:
        if label not in text:
            module.fail(f"Alloy config does not assign required stream label: {label}")

    lowered = text.lower()
    # Alloy regex literals escape dots in structured names. Compare against a
    # normalized policy view so `db\.statement` proves `db.statement` coverage
    # without weakening the required redaction catalogue.
    normalized_policy = lowered.replace(r"\.", ".")
    for token in module.REQUIRED_REDACTION_TOKENS:
        if token.lower() not in normalized_policy:
            module.fail(f"Alloy redaction policy omits token class: {token}")

    # Parse only the nested values maps. This prevents `values` from being
    # mistaken for a stream label while still failing on any additional label.
    stage_label_blocks = re.findall(
        r"stage\.labels\s*\{\s*values\s*=\s*\{(.*?)\}\s*\}",
        text,
        flags=re.DOTALL,
    )
    if len(stage_label_blocks) != 2:
        module.fail("Alloy must have exactly two dynamic label stages")
    for block in stage_label_blocks:
        label_names = set(
            re.findall(
                r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=",
                block,
                flags=re.MULTILINE,
            )
        )
        if label_names != {"application", "service"}:
            module.fail(f"unsafe dynamic Alloy labels: {sorted(label_names)}")

    if re.search(
        r"(?m)^\s*(trace_id|correlation_id|request_id|customer_id|user_id|email|phone)\s*=",
        text,
    ):
        module.fail(
            "high-cardinality or personal fields may not be assigned as stream labels"
        )


def main() -> None:
    module = load_validator()
    module.validate_runtime()
    validate_alloy_config(module)
    module.validate_compose()
    module.validate_packaging_and_docs()
    module.validate_secret_safety()
    print("Codestra Alloy corporate agent validation PASS")


if __name__ == "__main__":
    main()
