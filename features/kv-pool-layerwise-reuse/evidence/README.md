# Ranged API Validation Evidence

This directory contains the immutable evidence captured by the ranged API
validation runs. The files were imported byte-for-byte from their verified
workspace-external archives.

## G0-G3

- Report: [ranged-api-validation-2026-07-23.md](../ranged-api-validation-2026-07-23.md)
- Evidence: [ranged-api-20260723T094716Z](ranged-api-20260723T094716Z/SHA256SUMS)
- `SHA256SUMS` digest:
  `e5b4a768485f1aaf2b39d7421ab1c2f1308077f06f8f010f059a640cfb95d1f9`

## G4

- Report:
  [ranged-api-g4-validation-2026-07-23.md](../ranged-api-g4-validation-2026-07-23.md)
- Evidence:
  [ranged-api-g4-20260723T132919Z](ranged-api-g4-20260723T132919Z/runtime-audit/SHA256SUMS)
- `SHA256SUMS` digest:
  `af533b69d6128088bad74dc12dfab95fd31201882ae92577cf0c5908f754181d`

Verify from the control-repo root:

```bash
cd features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z
sha256sum -c SHA256SUMS

cd ../ranged-api-g4-20260723T132919Z/runtime-audit
sha256sum -c SHA256SUMS
```

Do not edit evidence files in place. A changed artifact requires a new run
identity and a regenerated checksum manifest.
