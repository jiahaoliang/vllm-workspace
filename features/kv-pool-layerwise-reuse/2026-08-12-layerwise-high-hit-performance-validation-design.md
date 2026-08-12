# Mooncake Layerwise High-Hit Performance Validation Design

## Decision

The next performance run compares `BULK`, `LAYERWISE`, and `REUSE3` under the
same measured Prefill workload with an exact external Prefix KV hit rate of
`81.25%`. The accepted generation-12 five-point results remain historical
cold-cache characterization and do not answer this high-hit question.

## Question

For 16,384-token Prefill requests whose first 13,312 tokens already exist in
Mooncake, how do the following configurations compare?

| Variant | Mooncake settings | Compute-side buffers |
| --- | --- | --- |
| `BULK` | `use_layerwise=false` | one independent buffer per layer |
| `LAYERWISE` | `use_layerwise=true` | one independent buffer per layer |
| `REUSE3` | `use_layerwise=true` | `layerwise_num_shared_buffers=3` on Prefill |

All other runtime settings, the exact prompts, topology, hardware placement,
client, and measurement procedure remain identical.

## Frozen Matrix

| Topology | Input | Output | Concurrency | Warmup | Seed | Formal | Repetitions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DP1/TP2 | 16,384 | 1 | 8 | 8 | 64 | 64 | 1 |

The three formal points are:

- `dp1-16384-bulk-o1-c8`
- `dp1-16384-layerwise-o1-c8`
- `dp1-16384-reuse3-o1-c8`

There is no automatic retry, outlier removal, performance timeout, or
statistical-significance claim.

## Exact Hit Construction

The block size is 128 tokens. Each formal prompt contains 128 blocks. Its seed
request contains the exact first 104 token blocks:

```text
13,312 / 16,384 = 104 / 128 = 81.25%
```

The fixture generator builds each 16,384-token formal prompt first and derives
the paired 13,312-token seed from `formal_token_ids[:13312]`. Both strings must
round-trip through the locked tokenizer to those exact token sequences. The
manifest and `metadata.jsonl` retain all token IDs and per-pair digests so the
relationship can be replayed without trusting the generator.

## Lifecycle

Each variant executes independently:

```text
start Prefill and Decode
-> correctness canary
-> warmup 8
-> clear Mooncake
-> seed 64 paired 13,312-token prefixes (not measured)
-> wait for master_key_count=6,656
-> record Prefill log byte offset
-> formal 64 paired 16,384-token prompts (measured; no clear)
-> capture only new Prefill log bytes
-> stop engines and wait for HBM release
```

`6,656 = 64 * 104` is valid for this frozen DeepSeek-V2-Lite MLA/TP2 layout:
`put_step=2`, so one Mooncake publication key is created for each prompt block.
The seed visibility probe waits until all keys have been published and rejects
any count above the exact target.

## External-Hit Oracle

All variants run with `--no-enable-prefix-caching`. Therefore the Prefill
engine cannot satisfy the paired prefix from its local vLLM prefix cache.

For every one of the 64 formal request IDs, the new Prefill log window must
contain exactly one scheduler record with:

```text
Total tokens 16384
kvpool hit tokens: 13312
need to load: 13312
```

In the scheduler, `need to load = external hit - local HBM hit`. Requiring both
values to be 13,312 proves both the 81.25% external hit and zero local-prefix
contribution. Missing, duplicate, extra, or mismatched records invalidate the
point before it can enter the report.

## Interpretation Boundary

This run compares high-hit transfer and Prefill behavior at concurrency 8. It
can reveal whether Layerwise transfer overlaps useful work better than Bulk at
this point. It is not a capacity-pressure test: `c8` may not consume enough KV
capacity for REUSE3's 5.4x logical-memory factor to increase admitted
concurrency. Any REUSE3 capacity claim requires a separate constrained-capacity
matrix.

The accepted output is a single-repetition raw characterization. Report direct
ratios for `LAYERWISE/BULK`, `REUSE3/LAYERWISE`, and `REUSE3/BULK`, but do not
assign a performance PASS/FAIL threshold.

## Acceptance Gates

- Exact source, image, node, namespace, model, and runtime identities replay.
- Shared fixtures contain 8 warmup, 64 seed, and 64 formal rows with 136 unique
  IDs and 64 exact token-prefix pairs.
- Each variant completes 64/64 seed and 64/64 formal requests.
- Seed publication reaches exactly 6,656 Mooncake keys.
- Each point contains 64/64 exact 13,312/16,384 external-hit records and zero
  inferred local-hit tokens.
- The evidence checker and both fixture/root checksum manifests replay.
- Engines stop, the original Kubernetes resources are restored, and Mooncake
  returns empty.

If startup or execution fails, this final cleanup gate does not run
automatically. The runner records `failed_environment_preserved=true` and
leaves the current Prefill/Decode Pods and logs intact for diagnosis. An
operator performs cleanup only after inspecting the failure.
