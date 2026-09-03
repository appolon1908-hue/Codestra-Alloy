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
    def test_build_helper_consumes_declared_manifest(self)->None:
        helper=(ROOT/"scripts/build_and_inspect_locked_image.sh").read_text()
        self.assertIn('manifest="codestra/release/image-build.v1.json"',helper)
        self.assertIn(".dockerfile | select",helper)
        self.assertIn(".context | select",helper)
        self.assertIn('--file "$dockerfile"',helper)
        subprocess.run(["bash","scripts/build_and_inspect_locked_image.sh","--validate-manifest"],cwd=ROOT,check=True)
    def test_private_http_boundary_is_built_and_configured(self)->None:
        compose=yaml.safe_load((ROOT/"codestra/deploy/compose.candidate.yaml").read_text())
        command=compose["services"]["alloy"]["command"]
        self.assertIn("--server.http.listen-addr=127.0.0.1:12346",command)
        self.assertIn("--server.http.disable-support-bundle",command)
        self.assertIn("--server.http.enable-pprof=false",command)
        dockerfile=(ROOT/"codestra/deploy/Dockerfile").read_text()
        self.assertIn('ENTRYPOINT ["/alloy-entrypoint"]',dockerfile)
if __name__=="__main__": unittest.main()
