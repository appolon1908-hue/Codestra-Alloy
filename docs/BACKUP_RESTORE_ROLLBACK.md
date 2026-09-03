# Backup, restore, and rollback

Preserve the Alloy WAL/state volume, reviewed configuration, source/image locks, both configuration and image digests, mounted secret-file paths, and release evidence without secret contents. Verify the previous image and configuration remain available before change.

Rollback by rendering the previous protected manifest with its exact image digest, restoring compatible Alloy state if required, and applying the matched Alloy plus read-only proxy services without rebuilding or deleting volumes. The previous manifest is eligible only when native Alloy remains bound to `127.0.0.1:12345` and the private `12346` proxy denies GET/POST `/-/reload`, GET `/-/support`, and every unlisted route. Prove those denials from an attached private peer together with allowed readiness, Prometheus metrics, Loki delivery, Tempo forwarding where configured, bounded labels, and backlog recovery.
