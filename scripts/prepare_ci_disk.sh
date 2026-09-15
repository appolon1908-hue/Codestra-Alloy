#!/usr/bin/env bash
# Reclaim preinstalled SDKs only on disposable GitHub-hosted runners.
set -Eeuo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_ENVIRONMENT:-}" != github-hosted ]]; then
  echo 'ALLOY_CI_DISK_CLEANUP=SKIPPED_NON_HOSTED_RUNNER'
  exit 0
fi
df -h /
sudo rm -rf -- /usr/local/lib/android /usr/share/dotnet /opt/ghc /opt/hostedtoolcache/CodeQL
available_kib="$(df -Pk / | awk 'NR == 2 {print $4}')"
if (( available_kib < 30 * 1024 * 1024 )); then
  echo 'ALLOY_CI_DISK=INSUFFICIENT_REQUIRES_30_GIB' >&2
  exit 1
fi
df -h /
echo 'ALLOY_CI_DISK=PASS'
