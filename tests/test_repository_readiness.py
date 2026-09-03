from __future__ import annotations
import json, subprocess, unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
class ReadinessTests(unittest.TestCase):
    def test_validator(self)->None: subprocess.run(["python3","scripts/validate_repository_readiness.py"],cwd=ROOT,check=True)
    def test_release_job_is_structurally_pinned(self)->None:
        job=yaml.safe_load((ROOT/".github/workflows/release-image.yml").read_text())["jobs"]["release"]
        self.assertEqual(job["with"]["image_id"],"alloy"); self.assertTrue(job["uses"].endswith("@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd"))
    def test_source_and_build_locks_agree(self)->None:
        upstream=json.loads((ROOT/"CODESTRA_UPSTREAM_LOCK.json").read_text()); lock=json.loads((ROOT/"codestra/release/runtime-base.lock.json").read_text()); manifest=json.loads((ROOT/"codestra/release/image-build.v1.json").read_text())
        self.assertEqual(lock["sourceAuthorityCommit"],upstream["upstream_commit"]); self.assertEqual(manifest["buildArgs"]["GO_BUILDER_IMAGE"],lock["builderImage"]); self.assertFalse(lock["runtimeBaseExecutableUsed"])
    def test_fixture_exclusions_are_bilateral(self)->None:
        dockerignore=(ROOT/".dockerignore").read_text(); gitleaks=(ROOT/".gitleaks.toml").read_text()
        self.assertIn("upstream/**/testdata*/",dockerignore); self.assertIn("testdata",gitleaks); self.assertIn("upstream/**/*_test.go",dockerignore)
    def test_native_admin_is_loopback_only_behind_read_only_proxy(self)->None:
        compose=yaml.safe_load((ROOT/"codestra/deploy/compose.candidate.yaml").read_text()); services=compose["services"]
        self.assertEqual(set(services),{"alloy","alloy-readonly-proxy"})
        self.assertIn("--server.http.listen-addr=127.0.0.1:12345",services["alloy"]["command"])
        self.assertEqual(set(map(str,services["alloy"]["expose"])),{"12346"})
        self.assertEqual(services["alloy-readonly-proxy"]["network_mode"],"service:alloy")
        self.assertEqual(services["alloy-readonly-proxy"]["entrypoint"],["/alloy-readonly-proxy"])
    def test_exact_image_build_uses_manifest_paths_and_denial_probe(self)->None:
        source=(ROOT/"scripts/build_and_inspect_locked_image.sh").read_text()
        for token in (".dockerfile",".context",'--file "$dockerfile"','"$context"',"docker network create --internal","http://alloy-readonly:12345","http://alloy-readonly:12346","ALLOY_HEALTHCHECK_EXPECT_STATUS=403","ALLOY_HEALTHCHECK_METHOD=POST"):
            self.assertIn(token,source)
if __name__=="__main__": unittest.main()
