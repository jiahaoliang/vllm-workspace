# External Artifact Manifests

This directory tracks checksums and archive status for large artifacts that
are intentionally not committed to Git. A manifest is not accepted evidence
of durable publication until its metadata records a persistent workspace-
external path and a successful checksum replay at that destination.
Metadata may instead record an explicit decision not to persist a payload; in
that case the manifest is only an inventory of the transient staging data.

- `layerwise-issue1-direct-20260814-rerun-archive-metadata/`: transient raw
  direct four-point evidence inventory.
- `layerwise-issue1-load-timing-20260817T181503+0800/`: compact archived
  load-timing analysis products plus the transient 723 MiB raw evidence
  inventory.
