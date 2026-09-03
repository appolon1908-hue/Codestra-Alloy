# Upgrade procedure

Synchronize upstream source through the reviewed source-authority workflow. Verify official and imported tree identities, update the builder/runtime locks and build manifest on a feature branch, and build the exact image locally and in exact-head CI. The build helper must read its Dockerfile and context from the reviewed image manifest; hard-coded alternate build paths are not release evidence.

Promote the same certified lineage through development, test, staging, production, and main. Staging must exercise telemetry redaction, file and journal permissions, backpressure, restart recovery, private exposure, allowed readback through port `12346`, peer denial of reload/support and unlisted routes, correlation-field preservation, and rollback before production authorization.
