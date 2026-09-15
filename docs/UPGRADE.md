# Upgrade procedure

Synchronize upstream source through the reviewed source-authority workflow. Verify official and imported tree identities, update the builder/runtime locks and build manifest on a feature branch, and build the exact image locally and in exact-head CI.

Promote the same certified lineage through development, test, staging, production, and main. Staging must exercise telemetry redaction, file and journal permissions, backpressure, restart recovery, private exposure, correlation-field preservation, and rollback before production authorization.
