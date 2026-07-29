# DeepSeek Multi-group KV Cache Research

Source:

- DeepSeek-V2 MLA paper: <https://arxiv.org/html/2405.04434v5#S2.SS1>
- DeepSeek-V3 official repository and inference implementation:
  <https://github.com/deepseek-ai/DeepSeek-V3/tree/9b4e9788e4a3a731f7567338ed15d3ec549ce03b>
- DeepSeek-V3.2 paper and official inference implementation:
  <https://arxiv.org/html/2512.02556v1#S2.SS1>,
  <https://github.com/deepseek-ai/DeepSeek-V3.2-Exp/tree/194c67e12b1b0d6df0ef373ddcf215bc84027409>
- DeepSeek-V4 paper and official Hugging Face inference implementation:
  <https://arxiv.org/html/2606.19348v1#S2.SS3>,
  <https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/tree/b5968e9190ef611bbf34a7229255be88a0e937c1>
- Native Sparse Attention paper: <https://arxiv.org/html/2502.11089v2>
- vLLM v0.24.0 baseline `ee0da84ab9e04ac7610e28580af62c365e898389`:
  `KVCacheGroupSpec`, DeepSeek-V4 grouping, hybrid hit coordination, and
  Mooncake HMA support.
- vLLM-Ascend PR [#12083](https://github.com/vllm-project/vllm-ascend/pull/12083)
  and PR [#12147](https://github.com/vllm-project/vllm-ascend/pull/12147),
  merged as `af2eaddc5903ad80b20fb1e7bcd53f18f7384a78` and
  `c2a8d0c4676120888c8fc7ea72864a8f592c2f2f`.
- Workspace source baselines: vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`,
  vLLM-Ascend `3f0cbf59cdcb8fa57091e17e9dce87cf215aa2c6`, and Mooncake
  `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`.

Captured At: 2026-07-28

Notes: Primary-source research for section 5.8 of the Mooncake layerwise
KVPool design. No model or NPU workload was run. The exact number and order of
runtime groups are implementation details derived from `KVCacheConfig`; the
design must not hard-code DeepSeek-specific group IDs.

## Conclusions

1. **`multi-group KV cache` is a vLLM runtime concept, not the name of a
   DeepSeek attention mechanism.** A `KVCacheGroupSpec` is a set of cache
   entries that share one block table. One physical transformer layer may
   contribute more than one cache tensor to the same group.
2. DeepSeek-V3 has a uniform MLA cache. DeepSeek-V3.2 adds a Lightning Indexer
   cache, but its main MLA cache and indexer cache can still share one vLLM
   group because they have the same token-slot and block-table semantics.
   Therefore, the existing section 5.8 wording that MLA latent and indexer
   necessarily belong to different groups is incorrect.
3. DeepSeek-V4 is the model that requires multiple groups: C4 compressed sparse
   attention, C128 heavily compressed attention, the C4 indexer, per-layer SWA,
   and C4/C128 compressor tail states have different sizes, compression ratios,
   block sizes, or retention rules.
4. Store operations can be isolated by `(group, key)`, but a cached prefix can
   be consumed only when all group state required by the selected recovery
   policy is available. Keeping successful writes from other groups is valid;
   consuming a partially loaded logical prefix is not.
5. For Mooncake layerwise objects, key, object size, range offset, session, and
   completion state must all be group-local. Size and offset must come from the
   group's actual packed cache entries, not from a universal
   `page_size * physical_layer_count` formula.

## 1. What a vLLM KV Cache Group Is

vLLM defines `KVCacheGroupSpec` as model layers that share the same KV cache
block table and are treated as one manager layer. It is an allocation and
scheduling boundary, not necessarily one model-side tensor or one attention
branch:

- [`KVCacheGroupSpec`](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/v1/kv_cache_interface.py#L864-L876)
- [`UniformTypeKVCacheSpecs`](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/v1/kv_cache_interface.py#L743-L799)

`UniformTypeKVCacheSpecs` may contain multiple cache entries with different
page sizes. Its `page_size_bytes` is the **sum** of the contained entries. The
entries can share a block table when they require the same token slots and have
the same block size. Consequently:

- one group may contain both a main attention cache and an indexer cache;
- a physical layer may have multiple cache entries inside that group;
- `group_id` is not a semantic label such as `MLA` or `indexer`;
- group count and order are derived from the model config and grouping code.

When the cache is heterogeneous, vLLM creates multiple groups and computes a
prefix hit by iteratively reducing the candidate length across attention-group
managers. The result is the common usable prefix, aligned to the groups' block
sizes; it is not the maximum hit of any one group:

- [DeepSeek-V4 group construction](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/v1/core/kv_cache_utils.py#L1499-L1670)
- [hybrid hit fixed-point calculation](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/v1/core/kv_cache_coordinator.py#L622-L732)

"All groups must be complete" therefore means all chunks that each group's
manager says are required at the candidate boundary. It does not mean that
every group must store an object at every hash-block position. SWA and other
state-like groups can have group-specific reachable/load masks.

## 2. DeepSeek Model Cache Layouts

### 2.1 DeepSeek-V3: MLA

DeepSeek-V3 adopts Multi-head Latent Attention (MLA). The optimized `absorb`
layout in the official inference code stores, for each layer and original
token:

- a latent KV vector of `kv_lora_rank = 512`;
- a separate RoPE key component of `qk_rope_head_dim = 64`.

See the official
[`MLA` cache allocation and use](https://github.com/deepseek-ai/DeepSeek-V3/blob/9b4e9788e4a3a731f7567338ed15d3ec549ce03b/inference/model.py#L396-L495).
The separate RoPE component is required because RoPE does not commute with the
low-rank key projection, as described in the
[MLA paper](https://arxiv.org/html/2405.04434v5#S2.SS1).

All attention layers use the same full-sequence cache semantics. In vLLM this
normally becomes one uniform group. MLA reduces each token's stored width; it
does not by itself imply multiple cache groups.

### 2.2 DeepSeek-V3.2: MLA plus Lightning Indexer

DeepSeek-V3.2-Exp introduces DeepSeek Sparse Attention (DSA), whose two stages
are:

1. a Lightning Indexer scores historical tokens and selects top-k positions;
2. the main MLA attention reads the selected entries and computes attention.

The official implementation retains the V3-style main cache (`512` latent plus
`64` RoPE) and adds an indexer cache per layer and token:

- `k_cache`: one 128-dimensional FP8 index key;
- `k_scale_cache`: one FP32 scale for each 128-value key in the demo layout.

Evidence:

- [DSA design, paper section 2.1](https://arxiv.org/html/2512.02556v1#S2.SS1)
- [official indexer cache and top-k](https://github.com/deepseek-ai/DeepSeek-V3.2-Exp/blob/194c67e12b1b0d6df0ef373ddcf215bc84027409/inference/model.py#L435-L487)
- [official main MLA cache and indexer consumption](https://github.com/deepseek-ai/DeepSeek-V3.2-Exp/blob/194c67e12b1b0d6df0ef373ddcf215bc84027409/inference/model.py#L498-L605)
- [vLLM indexer cache spec](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/model_executor/models/deepseek_v2.py#L574-L659)

These are two required cache **components**, but not necessarily two groups.
vLLM represents both as `MLAAttentionSpec` with the same block size, so it can
place them in one `UniformTypeKVCacheSpecs` group and sum their pages. This is
the first important correction to the existing section 5.8 background.

### 2.3 DeepSeek-V4: CSA, HCA, Indexer, SWA, and Tail State

DeepSeek-V4 replaces the uniform full-sequence layout with hybrid attention:

- **CSA / C4A:** every 4 original tokens produce one compressed 512-dimensional
  main attention entry. CSA uses DSA over compressed entries.
- **C4I:** CSA also produces a compressed indexer key with a distinct
  128-dimensional embedding. C4A and C4I use the same compressed positions and
  can share one block table, while remaining separate cache entries.
- **HCA / C128A:** every 128 original tokens produce one 512-dimensional main
  attention entry. HCA performs dense attention over these heavily compressed
  entries and has no Lightning Indexer.
- **SWA:** every physical layer retains a window of the latest 128 original
  tokens.
- **Compressor state:** until a 4- or 128-token compression unit is complete,
  the pending KV and score state must be retained. C4 compression overlaps
  adjacent windows, so its state layout differs from C128.

The V4 paper explicitly calls these "multiple types of KV entries with
different cache sizes and update rules" and separates classical CSA/HCA cache
from the SWA/unready-tail state cache:

- [CSA and compressed indexer keys](https://arxiv.org/html/2606.19348v1#S2.SS3.SSS1)
- [HCA](https://arxiv.org/html/2606.19348v1#S2.SS3.SSS2)
- [heterogeneous KV and state cache](https://arxiv.org/html/2606.19348v1#S3.SS5.SSS1)
- [official V4 inference model](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/b5968e9190ef611bbf34a7229255be88a0e937c1/inference/model.py#L279-L533)

For the official V4-Pro config captured above, the backbone has 61 layers:
30 C4 layers and 31 C128 layers; a trailing `0` compression entry is for MTP.
The current Ascend grouping logic splits MLA specs by compression ratio and
splits SWA/state specs by block size. Together with layer-tuple packing this
produces the six groups reported by vLLM-Ascend PR #12083:

| Runtime category | Contents | Why separate |
|---|---|---|
| C4 MLA group | C4A main cache plus C4I indexer cache | compression ratio 4; two entry widths sharing a block table |
| C128 MLA group | C128A main cache | compression ratio 128; no indexer |
| SWA group A | a partition of physical-layer SWA caches | full-token window semantics and allocator tuple packing |
| SWA group B | remaining physical-layer SWA caches | second allocator partition for the 61-layer layout |
| C4 state group | C4 main/indexer compressor tail state | C4-specific block size and overlap rule |
| C128 state group | C128 compressor tail state | C128-specific block size and update rule |

The group numbers and the fact that there are exactly six are not a connector
contract. The implementation must iterate `kv_cache_config.kv_cache_groups`,
use the group's builders and layer mapping, and tolerate a different count or
order. MTP layers are excluded from object sizing and normal layerwise
callbacks by PR #12083/#12147.

### 2.4 NSA Is Not the Group Model

Native Sparse Attention (NSA) combines compressed coarse tokens, selected
fine-grained blocks, and a sliding-window branch. It is a separate attention
architecture described in [the NSA paper](https://arxiv.org/html/2502.11089v2),
not vLLM's `kv_cache_groups` abstraction.

DeepSeek-V3.2 and V4 use DSA with a Lightning Indexer. V4's CSA applies DSA to
compressed entries. NSA's three branches must not be translated directly into
three Mooncake groups.

## 3. Prefix Completeness and Consumption

For a zero-recompute cache hit, a layer can run only when all state required by
its attention path is ready:

- V3.2 cannot select top-k without the indexer cache and cannot compute the
  selected attention without the main MLA cache.
- V4 C4 attention needs the C4 indexer result, C4 main compressed entries, and
  the relevant SWA/state data.
- V4 C128 attention needs C128 main entries and its relevant SWA/state data.

Thus the reusable prefix is the intersection of group-valid prefixes under the
group-specific masks and effective block sizes. A successful load from one
group does not make the same logical prefix valid if another required group
failed.

DeepSeek-V4 section 3.5.2 describes alternative disk policies that store all,
periodic, or no SWA entries and then explicitly recompute tail state. That is a
separate recovery protocol. Section 5.8 currently proposes full layerwise
transfer and does not implement V4's SWA/tail reconstruction algorithm, so it
must not treat absent state groups as directly consumable.

## 4. Implications for Mooncake Layerwise Objects

### 4.1 Key and Object Boundary

Use one object per `(model/cache namespace, group_id, block_hash,
head_or_tp_rank)`. vLLM's non-layerwise Mooncake HMA implementation likewise
includes `group_id` in `KeyMetadata` and in the serialized key:

- [Mooncake HMA group-aware key](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/data.py#L98-L150)

The layerwise key can retain the existing section 5.8 form:

```text
{model}@{group_id}@{block_hash}@{head_or_tp_rank}
```

Single-group compatibility can retain the current legacy key format, but all
producer, consumer, and scheduler paths must make the same decision.

### 4.2 Object Size

For group `g`, object size is the total bytes of every cache entry serialized
for one group block:

```text
object_size[g] = max(range_offset + range_size for all ranges in group g)
```

With a dense packing this is the sum of the group-local entry sizes. The
non-layerwise vLLM Mooncake implementation builds a multi-buffer value and lets
the object size be the sum of those actual buffer sizes rather than deriving an
average page:

- [group-local address/size construction](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/data.py#L182-L200)
- [per-group object put](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/worker.py#L611-L656)

`page_size[g] * num_layers[g]` is valid only when `page_size[g]` already means
the complete, constant **layer-tuple page** for that group. It is not valid if
`page_size[g]` is an average or if it ignores multiple cache entries in one
physical layer. C4A and C4I are the concrete counterexample.

### 4.3 Range Offsets

Offsets must be produced by the same group-local packing metadata used to
calculate object size:

```text
layer_tuple_offset = prefix_sum(layer_tuple_sizes)[layer_idx_in_group]
cache_inner_offset = prefix_sum(cache_entry_sizes_within_tuple)[entry_idx]
range_offset = layer_tuple_offset + cache_inner_offset
```

For the current DSV4 grouping, a C4 physical layer has at least the C4A and
C4I cache entries in the same group. The builder must transfer both entries at
different inner offsets. A single `layer_idx_in_group * page_size[g]` formula
is safe only after proving that every layer tuple has the same combined page
size and then still adding each entry's inner offset.

The connector should consume offsets emitted by the existing per-group builder
instead of rebuilding layout rules from DeepSeek names or compression ratios.

### 4.4 Hit Lookup

Lookup must:

1. derive hashes at each group's effective block size;
2. query every required TP/PP/rank key for that group;
3. apply the group's reachability/lookup mask;
4. feed the `(group_id, hash)` presence set to the hybrid coordinator, or
   equivalently compute the common aligned prefix with the same semantics;
5. return only the common usable token length.

The official vLLM Mooncake HMA coordinator treats a block as present only when
every group sharing a spec has it and reduces the candidate hit across all
attention groups:

- [external group-aware block pool](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/coordinator.py#L28-L51)
- [group-aware lookup](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/distributed/kv_transfer/kv_connector/v1/mooncake/store/worker.py#L1375-L1447)

## 5. Failure Semantics

### 5.1 Write Path

Failure isolation and publication are both per key:

1. `batch_put_start(keys, object_sizes)` returns an aligned result per key.
2. Only successfully started keys enter the active put-session set.
3. If any required range copy for a key fails, stop scheduling further ranges
   for that key and call `batch_put_revoke` for that key.
4. Call `batch_put_end` only after **all** required ranges of that key have
   succeeded.
5. Other group/key objects may complete and remain `COMPLETE`.

Keeping successful group objects is correct. A later lookup will only expose
the common prefix for which all required groups are available, so an isolated
successful object cannot be consumed as a complete logical prefix by itself.

### 5.2 Read Path

Read transport failures are also isolated per `(group, key)`, but consumption
success is evaluated at the logical-prefix level:

1. Track successful `batch_get_start` sessions per key.
2. A start or range-copy failure marks that `(group, key)` failed without
   cancelling unrelated keys or requests in the same batch.
3. Map every failed `(group, key)` to its request and original-token interval.
4. The affected logical interval is invalid for the request even when other
   groups loaded successfully. Attention must not consume the partial state.
5. Call `batch_get_end` exactly once for every successfully opened read
   session, including error and cancellation paths.

This is the same group/key isolation policy as writing. The difference is that
an unconsumed stored object may safely exist alone, while model execution needs
the complete set of required state.

### 5.3 Current Hybrid Load-failure Constraint

The existing `invalid_block_ids: set[int]` contract is not group-aware. The
upstream scheduler's failure handler contains a hybrid-memory TODO and unpacks
exactly one group:

- [scheduler invalid-block handling](https://github.com/vllm-project/vllm/blob/ee0da84ab9e04ac7610e28580af62c365e898389/vllm/v1/core/sched/scheduler.py#L2451-L2537)

vLLM-Ascend also explicitly rejects `kv_load_failure_policy="recompute"` for a
hybrid model in `vllm_ascend/platform.py`. The current whole-key multi-group
receive path logs hybrid failures and skips the invalid-block fallback to avoid
a scheduler crash (`kv_transfer.py`, around the branch that logs
`Skip invalid-block fallback to avoid scheduler crash`). Silently continuing
would leave partial or uninitialized state available to attention and is not an
acceptable section 5.8 outcome.

Therefore the implementation plan must choose one explicit contract before
enabling multi-group reads:

- **Recommended scoped contract:** propagate a group-aware request load failure
  and fail only the affected request under the existing default
  `kv_load_failure_policy="fail"`; other requests continue. Do not advertise
  hybrid recompute.
- **Larger alternative:** extend the connector/scheduler contract to carry
  `(group_id, block_id)` or request/token-interval failures and implement
  hybrid-aware truncation/recompute across every group.

The larger alternative is not required to implement section 5.8 storage and
layerwise transfer. Reusing the current single-group `set[int]` fallback while
claiming recompute support would be incorrect.

## 6. Confirmed Implementation Direction

The section 5.8 implementation should be generic N-group orchestration driven
entirely by `KVCacheConfig` and registered cache metadata:

1. Build a group descriptor containing the effective block size, group-local
   hashes, unique physical-layer tuples, actual cache-entry sizes, inner
   offsets, object size, and builder.
2. Generate group-aware keys and keep `save_keys`, `load_keys`, session state,
   and per-key transfer status group-local.
3. Open put sessions with each descriptor's exact object size.
4. For each physical layer, execute every `(group_id, layer_idx_in_group)` task
   and use the builder-provided object offsets for all cache entries in that
   layer tuple.
5. Commit or revoke independently per key after the last required range for
   that key, not merely after a nominal physical layer number.
6. Compute hits through all required groups and return the common aligned
   prefix.
7. On read failure, preserve group/key transport isolation but fail closed for
   the affected request until a hybrid-aware recompute protocol exists.
8. Unit tests must include a group containing multiple cache entries per
   physical layer, different group block sizes/compression ratios, partial
   `put_start`, range-copy failure, partial `get_start`, read-copy failure,
   exactly-once end/revoke, and common-prefix truncation.

This direction supports DeepSeek-V4 without coupling the connector to the
current six-group layout and remains applicable to future hybrid cache models.
