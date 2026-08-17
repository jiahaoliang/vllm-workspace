# External Artifact Manifests

This directory tracks checksums and archive status for large artifacts that
are intentionally not committed to Git. A manifest is not accepted evidence
of durable publication until its metadata records a persistent workspace-
external path and a successful checksum replay at that destination.
Metadata may instead record an explicit decision not to persist a payload; in
that case the manifest is only an inventory of the transient staging data.
