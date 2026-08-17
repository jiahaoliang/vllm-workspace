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

The raw 689 MiB payload is intentionally not committed to Git. On 2026-08-17,
the user explicitly decided not to create a persistent external copy.
`archive.json` records that terminal retention decision. The payload remains
available only while the `/tmp` staging directory exists and is not recoverable
from Git after that directory is removed.

While the staging directory exists, verify it from that root with:

```bash
sha256sum -c RAW-SHA256SUMS
```
