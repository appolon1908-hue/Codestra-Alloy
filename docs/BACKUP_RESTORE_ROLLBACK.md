# Backup, restore, and rollback

Preserve the Alloy WAL/state volume, reviewed configuration, source/image locks, both configuration and image digests, mounted secret-file paths, and release evidence without secret contents. Verify the previous image and configuration remain available before change.

Rollback by rendering the previous protected manifest with its exact image digest, restoring compatible Alloy state if required, and applying only the Alloy service without rebuilding or deleting volumes. Prove readiness, Loki delivery, Prometheus metrics, Tempo forwarding where configured, bounded labels, and backlog recovery.
