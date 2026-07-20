# Mooncake Layerwise Design Errata

Canonical source:
<https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/HJGESQG4ze>

Local snapshot:
`snapshots/design-mooncake-layerwise-gva-put.md`

Recorded at: 2026-07-20

## Backend commit/revoke contract

The current canonical design §§2.4, 5.2, and 5.3 says that
`Backend.batch_commit()` / `Backend.batch_revoke()` return success by default
and that Memcache overrides them as no-ops. The adopted implementation contract
is stricter:

- unsupported Backend session/range methods raise `NotImplementedError`;
- `MooncakeBackend` maps commit/revoke to `batch_put_end` and
  `batch_put_revoke`;
- Memcache flat-GVA transfer does not call commit/revoke and therefore does not
  advertise those capabilities through successful no-ops.

This erratum records the intentional source/snapshot discrepancy. Update the
canonical HackMD first, then refresh the Markdown snapshot and remove this
erratum. Do not hand-edit the captured snapshot independently of its source.

## Transfer limits

The canonical design already states that Mooncake's initial ranged path does
not split transfers. `layerwise_max_transfer_blocks` and
`layerwise_max_transfer_bytes` currently limit only Memcache flat-GVA
`batch_copy`; setting them does not split Mooncake ranged requests. The vLLM
Ascend user guide and implementation plan must preserve this distinction.
