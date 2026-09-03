# Repository profile

- Authority: `appolon1908-hue/Codestra-Alloy`
- Component: `alloy`
- Artifact model: repository-built, signed immutable image
- Source: sanitized, tree-verified upstream commit `041d2911a30a53f2c9c0317333aedee108a56b0a`
- Runtime base role: libraries and filesystem only; its Alloy executable is replaced
- Exposure: private observability networks only; no host port, host network, host PID, privileged mode, or Docker socket
- Promotion: `development -> test -> staging -> production -> main`
- Production activation from this source: `NO`

Upstream documentation and test fixtures that contain example credential shapes are excluded from the Docker context and from release secret scanning through the reviewed `.dockerignore` and `.gitleaks.toml`; runtime source remains included.
