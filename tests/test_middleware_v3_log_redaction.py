"""Middleware V3 log redaction: every credential class is removed, drilldown fields survive, contract stays dark."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_middleware_v3_log_redaction", ROOT / "scripts" / "validate_middleware_v3_log_redaction.py"
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class LogRedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = VALIDATOR.CONFIG.read_text(encoding="utf-8")
        cls.stages = VALIDATOR.parse_stages(cls.text)
        cls.contract = json.loads(VALIDATOR.CONTRACT.read_text(encoding="utf-8"))

    def redact(self, line: str, service: str = "middleware") -> str | None:
        return VALIDATOR.redact(line, self.stages, service)

    def test_corpus_and_contract_pass(self) -> None:
        VALIDATOR.validate_corpus(self.stages)
        VALIDATOR.validate_contract(self.contract, self.text)

    def test_pins(self) -> None:
        self.assertEqual(self.contract["middleware"]["prep_base_sha"], "22d023a9c65b0789a0f7ee6c28548753521a9eff")
        self.assertEqual(self.contract["middleware"]["v3_final_sha"], "PENDING")
        self.assertEqual(self.contract["status"], "PREPARED_DISABLED")

    def test_compound_credential_keys(self) -> None:
        for key in ("smtp_password", "db_password", "redis_password", "provider_api_key", "x-api-key", "bao_token",
                    "aws_secret_access_key", "klyrow_client_secret", "telnexa_api_key", "service_account_credentials",
                    "postgres_dsn", "smtp_connection_string"):
            result = self.redact(f'{{"{key}":"PLANTED-VALUE-1234","service_id":"middleware"}}')
            self.assertIsNotNone(result, key)
            self.assertNotIn("PLANTED-VALUE-1234", result, key)
            self.assertIn("middleware", result, key)
            result = self.redact(f"{key}=PLANTED-VALUE-1234 service_id=middleware")
            self.assertNotIn("PLANTED-VALUE-1234", result, key)
            self.assertIn("middleware", result, key)
            result = self.redact(f"{key.upper()}=PLANTED-VALUE-1234")
            self.assertNotIn("PLANTED-VALUE-1234", result, key)

    def test_connection_urls_and_basic_auth(self) -> None:
        for line in (
            "postgres://mw:PLANTEDPASS@postgres:5432/mw",
            "redis://:PLANTEDPASS@redis:6379/0",
            "smtp://mailer:PLANTEDPASS@smtp.internal:587",
            "amqps://nats:PLANTEDPASS@nats:4222",
            "https://user:PLANTEDPASS@provider.example/api",
            "Authorization: Basic UExBTlRFRFBBU1NQTEFOVEVE",
            "authorization=Basic UExBTlRFRFBBU1NQTEFOVEVE",
        ):
            result = self.redact(line)
            self.assertIsNotNone(result, line)
            self.assertNotIn("PLANTEDPASS", result, line)
            self.assertNotIn("UExBTlRFRFBBU1NQTEFOVEVE", result, line)

    def test_openbao_token_shapes(self) -> None:
        for token in ("hvs." + "A" * 30, "hvb." + "B" * 30, "s." + "c" * 26, "b." + "d" * 70):
            result = self.redact(f"login ok token={token}")
            self.assertNotIn(token, result, token)
            result = self.redact(f"X-Vault-Token: {token}")
            self.assertNotIn(token, result, token)

    def test_jwt_anywhere(self) -> None:
        jwt = "eyJ" + "a" * 20 + "." + "eyJ" + "b" * 20 + "." + "c" * 30
        self.assertNotIn(jwt, self.redact(f"forwarded {jwt} to adapter"))

    def test_reference_metadata_survives(self) -> None:
        line = ('{"secret_ref":"codestra/production/middleware/api/database","secret_class":"database_credentials",'
                '"reference_uri":"openbao://codestra/production/middleware/api/database","rotation_status":"current",'
                '"lease_id_hash":"sha256:abc","token_type":"bearer","token_count":3,"idempotency_key":"am:1",'
                '"correlation_id":"c-1","operation_id":"o-1","trace_id":"t-1","deployment_sha":"22d023a9"}')
        result = self.redact(line)
        self.assertEqual(result, line)

    def test_intake_services_drop_personal_payloads_but_middleware_keeps_correlation(self) -> None:
        line = '{"correlation_id":"c-1","email":"someone@codestra.co"}'
        self.assertIsNone(self.redact(line, service="middleware-intake"))
        result = self.redact(line, service="middleware")
        self.assertIsNotNone(result)
        self.assertIn("c-1", result)
        self.assertNotIn("someone@codestra.co", result)

    def test_private_key_material_is_dropped(self) -> None:
        self.assertIsNone(self.redact("-----BEGIN EC PRIVATE KEY-----"))
        self.assertIsNone(self.redact('{"credentials":{"password":"x"}}'))

    def test_v3_fields_are_structured_metadata_not_labels(self) -> None:
        import re

        metadata = re.findall(r"stage\.structured_metadata\s*\{\s*values\s*=\s*\{(.*?)\}\s*\}", self.text, flags=re.DOTALL)
        names = set()
        for chunk in metadata:
            names |= set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", chunk, flags=re.MULTILINE))
        self.assertTrue({"correlation_id", "operation_id", "trace_id", "span_id", "deployment_sha"} <= names)
        labels = set()
        for chunk in re.findall(r"stage\.labels\s*\{\s*values\s*=\s*\{(.*?)\}\s*\}", self.text, flags=re.DOTALL):
            labels |= set(re.findall(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=", chunk, flags=re.MULTILINE))
        self.assertEqual(labels, {"application", "service"})

    def test_contract_rejects_activation_and_label_leaks(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["activation_enabled"] = True
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.text)
        mutated = copy.deepcopy(self.contract)
        mutated["required_common_fields"]["operation_id"]["carried_as"] = "stream_label"
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.text)
        mutated = copy.deepcopy(self.contract)
        mutated["label_policy"]["never_labels"].remove("command_id")
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.text)
        mutated = copy.deepcopy(self.contract)
        del mutated["redaction"]["classes"]["smtp_credentials"]
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.text)


if __name__ == "__main__":
    unittest.main()
