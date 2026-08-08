# Mooncake Shared-Buffer Functional Acceptance

Run: `20260808T121828Z`

Status: **PASS**

## Frozen Identity

| Field | Value |
| --- | --- |
| Control tooling commit | `c8c3a242db83d78196d6ea2181fc848024eaba4f` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `a3c97358ccca51e6d9441c66ea5d4ff1bd1645e7` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-a3c97358-df3f74ed-20260808T121828Z` |
| Manifest | `sha256:32b379315a80c590dbaa563310fe70f8ee15a901abc9a67a9ad18c46fa22ef3c` |
| Config | `sha256:17b133d3e8ff668f567150ba755a587709e7d600c4bad3f6423f30b77b14f7f3` |
| Platform | `linux/arm64` |
| Namespace / node / physical NPU | `liangjiahao` / `n1` / `6` |

The image is an eight-file Python patch of the frozen `45b2e785` native base,
followed by `nerdctl commit`. The OCI metadata correction changed only config
and manifest metadata; all 22 filesystem layer descriptors remained unchanged.

## Acceptance Results

| Gate | Result |
| --- | --- |
| Complete AscendStore + exact MLA CPU/mock | `514 passed` |
| Layerwise config + cache-layout model-runner | `30 passed` |
| Deployment/performance mocks | `129 passed` |
| Performance harness | `44 passed` |
| Ruff / compile / diff check | PASS |
| No-reuse baseline | PASS |
| `kv_producer`, shared buffers = 3 | PASS |
| `kv_both` cold + warm, shared buffers = 3 | PASS |
| Exact response equality | PASS |
| Final Master cleanup after every case | `0/0/0` |
| NPU process release after every case | PASS |

All four responses were exactly:

```text
 The private audit marker is a marker that is used to indicate that the audit content
```

Each response used 525 prompt tokens and 16 completion tokens with
`finish_reason=length`.

## Layer Layout Proof

- Logical layers: `27`.
- Physical slots: `5` (`3` shared plus independent layers `0` and `26`).
- KV memory factor: `5.4`.
- `kv_producer`: 405 ranged loads across 15 ordered layer groups. Independent
  layers loaded one HBM-tail key per group; shared layers loaded five full-prefix
  keys per group.
- `kv_both`: 837 ranged loads across 31 ordered layer groups. The cold and warm
  decode groups retained the same 1/5-key split, and the warm prefix load used
  four keys for every layer.
- No whole-key transfer was observed.
- No save/load timeout, abort-drain failure, traceback, or corrupted response
  was observed.

## Preserved Failure Evidence

The earlier formal run `20260808T111904Z` failed exact response equality even
after load metadata was separated by HBM-tail layout. Diagnostic run
`shared-buffer-diagnostic-20260808T120204Z` proved layer 1 received five-key
metadata before the receiving thread filtered it to one active row. The final
fix changed the receiving-thread failure state from one global row-index set to
stable inactive row identities `(request, block, key)`. This preserves failed-row
filtering while allowing different shared-buffer layouts to carry different row
counts.

## Scope

Real NPU coverage is limited to `kv_producer` and `kv_both` on the named A2
hardware. CPU/mock coverage retains all configured role/default restrictions.
This report does not claim pure-consumer reuse, memcache regression coverage,
FabricMem, A3, Mooncake multi-group, or performance results.
