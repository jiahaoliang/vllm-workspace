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

## Multi-DP/TP Stress Validation

- Report:
  [multi-dp-tp-stress-validation-2026-07-25.md](../multi-dp-tp-stress-validation-2026-07-25.md)
- Result: failed closed on exact response equality; no production-source
  change or acceptance-gate reduction was made.
- Archived runs:
  [014317Z](ranged-api-stress-20260725T014317Z/README.md),
  [015720Z](ranged-api-stress-20260725T015720Z/README.md),
  [030454Z](ranged-api-stress-20260725T030454Z/README.md),
  [031659Z](ranged-api-stress-20260725T031659Z/README.md), and
  [033747Z](ranged-api-stress-20260725T033747Z/README.md).

Verify from the control-repo root:

```bash
cd features/kv-pool-layerwise-reuse/evidence/ranged-api-20260723T094716Z
sha256sum -c SHA256SUMS

cd ../ranged-api-g4-20260723T132919Z/runtime-audit
sha256sum -c SHA256SUMS

for evidence_dir in ranged-api-stress-20260725T*; do
  (cd "${evidence_dir}" && sha256sum -c SHA256SUMS)
done
```

Do not edit evidence files in place. A changed artifact requires a new run
identity and a regenerated checksum manifest.
