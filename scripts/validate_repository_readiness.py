#!/usr/bin/env python3
"""Validate repository-only Alloy image release readiness."""
from __future__ import annotations
import json, re
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
AUTHORITY = "appolon1908-hue/Codestra-Telemetry/.github/workflows/reusable-release-image.yml@9a6aebb849bbc068105c10d9d1dfd39ebf6f78bd"
REQUIRED = ("REPOSITORY_PROFILE.md","SECURITY.md",".github/CODEOWNERS","docs/BACKUP_RESTORE_ROLLBACK.md","docs/UPGRADE.md",".dockerignore",".gitleaks.toml","codestra/release/image-build.v1.json","codestra/release/runtime-base.lock.json",".github/workflows/release-image.yml","scripts/build_and_inspect_locked_image.sh","requirements-validation.txt")
def fail(message: str) -> None: raise SystemExit(f"ERROR: {message}")
def load(path: str) -> dict:
    value=json.loads((ROOT/path).read_text())
    if not isinstance(value,dict): fail(f"{path} must contain an object")
    return value
def validate() -> None:
    missing=[p for p in REQUIRED if not (ROOT/p).is_file()]
    if missing: fail(f"missing readiness files: {missing}")
    manifest=load("codestra/release/image-build.v1.json"); lock=load("codestra/release/runtime-base.lock.json")
    if manifest.get("imageId")!="alloy" or manifest.get("context")!="." or manifest.get("dockerfile")!="codestra/deploy/Dockerfile" or manifest.get("productionActivation") is not False: fail("image manifest identity/context/activation mismatch")
    if not (ROOT/manifest["context"]).is_dir() or not (ROOT/manifest["dockerfile"]).is_file(): fail("image manifest path does not exist")
    if lock.get("artifactModel")!="repository-built-signed-image" or lock.get("productionActivation") is not False: fail("runtime lock model/activation mismatch")
    for field in ("buildFrontendImage","builderImage","runtimeBaseImage"):
        if not IMAGE.fullmatch(str(lock.get(field,""))): fail(f"mutable build input: {field}")
    if manifest.get("buildArgs")!={"ALLOY_BASE_IMAGE":lock["runtimeBaseImage"],"GO_BUILDER_IMAGE":lock["builderImage"]}: fail("manifest build arguments mismatch")
    upstream=load("CODESTRA_UPSTREAM_LOCK.json")
    if lock.get("sourceAuthorityCommit")!=upstream.get("upstream_commit") or lock.get("sourceOfficialTreeSha")!=upstream.get("official_tree_sha") or lock.get("sourceImportedTreeSha")!=upstream.get("imported_tree_sha"): fail("source tree authority mismatch")
    source_contract=load("codestra/source-image-contract.v1.json")
    if source_contract.get("builder",{}).get("digest") != lock["builderImage"].rsplit(":",1)[1]: fail("builder digest conflicts with source-image contract")
    if lock.get("runtimeBaseExecutableUsed") is not False: fail("runtime base executable may not be source authority")
    dockerfile=(ROOT/manifest["dockerfile"]).read_text()
    if dockerfile.splitlines()[0]!=f"# syntax={lock['buildFrontendImage']}": fail("Dockerfile frontend mismatch")
    if "COPY upstream /src/upstream" not in dockerfile or "/alloy-readonly-proxy" not in dockerfile or "COPY --from=alloy-builder" not in dockerfile: fail("source-built executable boundary missing")
    dockerignore=(ROOT/".dockerignore").read_text()
    for token in ("upstream/docs/","upstream/integration-tests/","upstream/**/testdata*/","upstream/**/*_test.go","upstream/internal/pipelinetest/"):
        if token not in dockerignore: fail(f"test fixture not excluded from build context: {token}")
    allowlist=(ROOT/".gitleaks.toml").read_text()
    if "useDefault = true" not in allowlist or "Official upstream documentation" not in allowlist: fail("secret-scan allowlist authority missing")
    release=yaml.safe_load((ROOT/".github/workflows/release-image.yml").read_text()); job=release.get("jobs",{}).get("release",{})
    if job.get("uses")!=AUTHORITY or job.get("with",{}).get("image_id")!="alloy": fail("release authority mismatch")
    build_call='bash scripts/build_and_inspect_locked_image.sh "$GITHUB_SHA"'
    for relative in (".github/workflows/validate-repository-readiness.yml", ".github/workflows/validate-repository-readiness-protected.yml"):
        if build_call not in (ROOT/relative).read_text(): fail(f"merge/protected image build missing: {relative}")
    build_script=(ROOT/"scripts/build_and_inspect_locked_image.sh").read_text()
    for token in (".dockerfile", ".context", '--file "$dockerfile"', '"$context"', "docker network create --internal", "http://alloy-readonly:12345", "http://alloy-readonly:12346", "ALLOY_HEALTHCHECK_EXPECT_STATUS=403", "ALLOY_HEALTHCHECK_METHOD=POST"):
        if token not in build_script: fail(f"exact-image validation omits manifest or route control: {token}")
    compose=yaml.safe_load((ROOT/"codestra/deploy/compose.candidate.yaml").read_text()); services=compose.get("services",{}); service=services.get("alloy",{}); proxy=services.get("alloy-readonly-proxy",{})
    if set(services)!={"alloy","alloy-readonly-proxy"}: fail("Alloy runtime must contain the collector and read-only proxy")
    if service.get("privileged") is True or service.get("network_mode")=="host" or service.get("pid")=="host" or service.get("ports"): fail("unsafe Alloy runtime boundary")
    if "--server.http.listen-addr=127.0.0.1:12345" not in service.get("command",[]) or set(map(str,service.get("expose",[])))!={"12346"}: fail("native Alloy listener is not loopback-only behind the read-only port")
    if proxy.get("network_mode")!="service:alloy" or proxy.get("entrypoint")!=["/alloy-readonly-proxy"] or proxy.get("ports"): fail("read-only proxy network boundary mismatch")
    for item in (service,proxy):
        if item.get("user")!="10001:10001" or item.get("read_only") is not True or "ALL" not in item.get("cap_drop",[]) or "no-new-privileges:true" not in item.get("security_opt",[]): fail("Alloy runtime hardening mismatch")
    for workflow in (ROOT/".github/workflows").glob("*.yml"):
        for ref in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)",workflow.read_text()):
            if not ref.startswith("./") and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}",ref): fail(f"mutable action: {workflow.name}: {ref}")
def main() -> None:
    validate(); print("ALLOY_REPOSITORY_READINESS_SOURCE=PASS"); print("ARTIFACT_MODEL=SIGNED_IMAGE"); print("PRODUCTION_ACTIVATION=NO")
if __name__=="__main__": main()
