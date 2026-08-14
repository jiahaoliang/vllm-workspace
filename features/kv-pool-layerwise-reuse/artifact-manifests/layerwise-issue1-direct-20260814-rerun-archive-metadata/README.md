# Lightweight REUSE3 Raw Artifact Metadata

This directory records the immutable manifest for the raw four-point evidence
staged at:

```text
/tmp/layerwise-issue1-direct-20260814-rerun/
```

`RAW-SHA256SUMS` contains 107 relative paths and covers 721,923,136 bytes. It
was generated and replayed successfully in the staging root on 2026-08-14.
The manifest itself has SHA256:

```text
85d60b3ffcde0593ca648f572d9833745aab523b3f07bf0abc62aef579603994
```

The raw 689 MiB payload is intentionally not committed to Git. Repository
policy requires it to be copied to a user-selected persistent path outside the
workspace and replayed there. `archive.json` records that the external copy is
pending because no persistent destination has been selected yet.

After copying the payload, verify it from the destination root with:

```bash
sha256sum -c RAW-SHA256SUMS
```

Then update `archive.json` with the persistent path, replay time and result.
