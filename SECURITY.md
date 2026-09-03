# Security policy

Report vulnerabilities privately through GitHub Security Advisories. Never publish runtime credentials, TLS keys, telemetry payloads, or exploit details in issues.

The release image is compiled from the verified imported source tree with the journal build tag. The Dockerfile frontend, builder, and runtime substrate are digest-pinned. Runtime credentials are mounted files, logs are redacted and business-scoped, and release requires vulnerability scanning, an SBOM, signature, provenance, exact revision labels, and protected production lineage.
