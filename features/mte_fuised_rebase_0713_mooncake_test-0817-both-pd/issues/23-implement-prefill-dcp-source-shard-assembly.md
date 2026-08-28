# 23 — 实现 Prefill DCP source shard assembly

**What to build:** 在 vLLM-Ascend `117637d205603b0c1e43aa0ea3e141de926ff3b1` 上扩展现有
`MooncakeConnectorV1 + dsa_pd_offload=true`，支持 Prefill SFA sparse、`PCP=1`、`DCP>1`，同时
Decode 保持 `DCP=1`、`PCP=1`、`PP=1`。Main 从 exact Prefill DCP source group 顺序拼装，Indexer
继续只从该 group 的 fixed replica leader 拉取。

**Spec:** [Blockwise DSA spec](../spec.md)

**Research basis:** [PR #14958 integration research](../research/11-pr-14958-integration.md)

**Blocked by:** None.

**Status:** claimed

## Fixed baseline

- Control repo branch: `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd`.
- vLLM-Ascend branch: `feature/blockwise-dsa-mooncake-v1-reimplementation`.
- Source baseline: `117637d205603b0c1e43aa0ea3e141de926ff3b1`.
- vLLM baseline: `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665`.
- Initial source state: clean. Initial control state: only unrelated untracked `deployment_yaml/`.
- Do not modify vLLM core, cache allocation, public connector schemas, ordinary `ReqMeta` /
  `GroupPull`, or the positional Main/Indexer handshake ABI.

## Accepted topology and routing

- Prefill: SFA sparse, `PCP=1`, `DCP>1`, and `P_DCP` divides `P_TP`.
- Decode: `DCP=1`, `PCP=1`, `PP=1`.
- Preserve `P_TP >= D_TP` and `P_TP % D_TP == 0`.
- For Decode TP rank `j`, let `group_count = P_TP / P_DCP` and
  `group_index = floor(j * group_count / D_TP)`. Main sources are the consecutive `P_DCP` ranks in
  that group; Indexer comes from the group's first rank.
- Multiple Decode TP ranks may share one Prefill DCP source group. `P_DCP=1` must reduce exactly to
  the current fixed-leader mapping.
- Prefill PCP, Decode CP, cross-Prefill-DP tensor mixing, mixed-version P/D deployment, retry,
  watchdog, and reliable cancel remain out of scope.

## Implementation checklist

- [ ] Add immutable `MainSourceSharding(dcp_size, block_size, interleave_size)` to typed DSA
  metadata and make `RemoteSource.main_sharding` optional; `None` preserves the complete-leader path.
- [ ] Publish `remote_cp_kv_cache_interleave_size` from Prefill and validate PCP/DCP/TP plus
  block/interleave geometry during Decode admission.
- [ ] Add a private pure source-plan module for source-group selection and rank-local Main token to
  Decode-global destination range planning.
- [ ] Validate source capacity and exact destination coverage before the first Main write: no overlap,
  gap, or out-of-bounds range; retain full physical transfer for a partial tail block.
- [ ] Build an immutable receive route before enqueue. Resolve and validate every endpoint before
  transfer; execute one leader Indexer D2D, then Main D2RH shards in Prefill-rank order, then emit one
  `RECEIVE_COMPLETE`.
- [ ] Preserve `TRANSFER_FAILED/INDEXER_D2D` and `TRANSFER_FAILED/MAIN_D2RH` classification without
  adding connector retry.
- [ ] Acquire stable-sorted per-endpoint locks for the whole multi-source set.
- [ ] Retain only selected Prefill source ranks, compute shared-group fanout through existing
  `remote_port_send_num`, and attempt one `DONE_RECVING_MSG` per planned endpoint in every terminal
  path, including failure and cancellation.
- [ ] Keep ordinary `dsa_pd_offload=false`, DSA DCP1, exact Decode-TP completion, async scheduling,
  replay, preemption, QUIESCE, and terminal release behavior unchanged.

## TDD and validation checklist

- [ ] Pure planner red-green: DCP1 legacy, DCP2/DCP4, shared source group, invalid TP/DCP geometry,
  interleave 1/block-size, asymmetric block sizes, and partial tail.
- [ ] Coverage red-green: each destination byte written once; exact union of bound Main blocks;
  insufficient source capacity, overlap, gap, and out-of-range fail before transfer.
- [ ] Receiver red-green: Indexer before Main, rank-ordered endpoint sessions, middle/final Main shard
  failure classification, and no `RECEIVE_COMPLETE` after any failure.
- [ ] Ownership red-green: selected-rank retention, shared-group fanout, and all-endpoint release on
  success/failure/cancellation.
- [ ] Lifecycle/isolation regressions: exact TP, async scheduling, replay, preemption, QUIESCE,
  ordinary V1, DSA DCP1 fixed leader, and positional registration.
- [ ] Run focused single-file tests and type/static checks throughout implementation.
- [ ] In the CPU-only long-running `liangjiahao/vllm-ascend-ut` Pod, tar-sync the exact checkout and
  explicitly run metadata, source planner, connector, and focused DSA/SFA targets with bytecode and
  pytest cache disabled.
- [ ] Run the full applicable CPU/mock suite once at the end and record baseline exclusions exactly.
- [ ] Run independent Standards and Spec review through `code-review`; resolve all blocking findings.
- [ ] Real Mooncake/NPU DCP2/DCP4, partial block, prefix cache, concurrency, cache-content, and output
  oracle remain `planned / not run` until actually executed.

## Documentation and publication checklist

- [ ] Add a new ADR that partially supersedes ADR 0004: fixed leader remains for Indexer; Main uses
  exact Prefill DCP shard assembly.
- [ ] Update the spec to remove the old multi-P shard exclusion and one-Mooncake-call-per-phase
  constraint while preserving positional ABI and deployment preconditions.
- [ ] Update the NPU validation plan with DCP2/DCP4 and the required cache-content/output oracles.
- [ ] Commit source changes on the current vLLM-Ascend feature branch.
- [ ] Refresh `workspace.lock.json` with `./scripts/lock-repos.sh`, update `repo-state.md`, this ticket,
  `status.md`, and `map.md`, then commit control-repo records with an explicit staging allowlist.
- [ ] Preserve unrelated `deployment_yaml/` and do not include `repos/*` source in the control commit.

## Evidence ledger

| Evidence | Status | Result / pointer |
| --- | --- | --- |
| Initial identity and dirty-state check | PASS | Recorded above; checked 2026-08-29 |
| Planner focused CPU/mock | pending | Not run |
| Connector/metadata focused CPU/mock | pending | Not run |
| Full applicable CPU/mock | pending | Not run |
| Static/type checks | pending | Not run |
| Independent code review | pending | Not run |
| Real Mooncake | `planned / not run` | No runtime claim |
| NPU serving/correctness/performance | `planned / not run` | No runtime claim |
| Source commit | pending | Not committed |
| Control repo state commit | pending | Not committed |

## Resume protocol

After interruption or compaction:

1. Read workspace `AGENTS.md`, `repos/vllm-ascend/AGENTS.md`, this ticket, `map.md`, `spec.md`, ADR
   0004 and the newest ADR added by this ticket.
2. Recheck both repo branches, HEADs, remotes, dirty state, `workspace.lock.json`, and
   `repo-state.md`. Treat newly observed edits as user-owned until proven otherwise.
3. Inspect this ticket's unchecked checklist and evidence ledger. Resume the first incomplete
   vertical slice; do not repeat completed validation unless source identity changed.
4. Keep static, CPU/mock, real Mooncake, NPU, serving, graph-capture, and performance evidence
   separate. Never upgrade `planned / not run` from a plan or mock result.
5. Before each commit, use an explicit staging allowlist and verify staged diff. Do not stage
   `deployment_yaml/` or any `repos/*` content in the control repo.

## Work log

- 2026-08-29: Claimed implementation ticket and persisted the user-approved plan before production
  edits. Verified the initial control/source identities and dirty-state boundaries.

## Answer

Pending implementation and validation.
