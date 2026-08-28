# PR #14958 集成调查：Prefill DCP-on / Decode DCP-off 的 SFA replicated-indexer transfer

Captured At: 2026-08-28 (Asia/Shanghai)

Source PR: [vllm-project/vllm-ascend#14958](https://github.com/vllm-project/vllm-ascend/pull/14958)

## 研究问题

如何把 PR #14958 提议的功能集成到本 workspace 当前代码：它实际修复什么、依赖哪些已有 contract、是否可以直接 cherry-pick、两条可能的“current code”分别会遇到什么冲突、与配套 vLLM 的 API 条件是什么，以及实现后需要怎样验证？

## 结论

**Decision**: 不应把 PR #14958 的 6 个提交直接 cherry-pick 到本 workspace 的任一 vLLM-Ascend checkout。它的最终 patch 依赖当前两条 checkout 都没有的 ordinary `MooncakeConnectorV1` replicated-indexer request/block plumbing；对两条 checkout 执行 cumulative patch 和首提交 patch 的 `git apply --check --verbose` 都失败，production file、tests 和首提交中的一个 scheduler patch path 均不匹配。

**Design gate**: 若目标是 `dsa_pd_offload=false` 的 ordinary `MooncakeConnectorV1`，实现前必须先决定 cache architecture。PR base 已包含 #11647：它把 SFA MLA 与 Indexer allocation 拆成 `AscendMLAAttentionSpec` 和 `AscendSFAIndexerCacheSpec`；当前 durable target 则仍把 Main/Indexer physical layout 打包在一个 `AscendMLAAttentionSpec` 中，并不存在 `AscendSFAIndexerCacheSpec`。因此只能二选一：完整 backport separated-cache-spec architecture，或保留当前 packed layout、设计一个显式且 fail-closed 的 connector semantic-role adapter。未做该决定前，不能把 #14958 的 `kv_cache_spec_type == "AscendSFAIndexerCacheSpec"` 当作可执行步骤。[#11647 commit](https://github.com/vllm-project/vllm-ascend/commit/c43bc7fa4091b6236410a87ea61103da15d71a8a) [current packed spec](../../../repos/vllm-ascend/vllm_ascend/core/kv_cache_interface.py#L218)

**Decision**: 在上述 gate 关闭后，推荐在 `117637d20` 上做 semantic backport，而不是逐提交解冲突：按 upstream topology 依次满足 #11647 的 cache-identity/allocation contract、#11696 的 replicated-indexer metadata/block-routing contract和 #13968 的 logical KV group、transfer group及独立 physical metadata-plane contract，最后应用 #14958 的 remote-DCP eligibility delta。三个 commit 都是 PR merge-base 已包含的 upstream prerequisites；#14836 的讨论也明确把 #13965（#13968 的 main 版本）列为前置。[#11647 commit](https://github.com/vllm-project/vllm-ascend/commit/c43bc7fa4091b6236410a87ea61103da15d71a8a) [#11696 commit](https://github.com/vllm-project/vllm-ascend/commit/c062a7e9fd9a5da377d9b86774ad3bdac9ef913b) [#13968 commit](https://github.com/vllm-project/vllm-ascend/commit/d4c8445b039e993214ee3c200557e56e4cb2f399) [#14836 prerequisite note](https://github.com/vllm-project/vllm-ascend/pull/14836#issuecomment-5440199282)

**Decision**: 若目标是 `dsa_pd_offload=true` 的 Blockwise DSA path，PR #14958 不是该功能的实现。Feature contract 要求 DSA metadata family 与普通 `MooncakeConnectorMetadata`/`ReqMeta` 隔离，并要求关闭 DSA 时普通 V1 行为不变；replacement source 的 DSA receive 也走 positional `DsaStepRequest` 和 `_execute_dsa_receive()`，不是 #14958 修改的 replicated-K request fields。[feature contract](../spec.md#mode-and-topology) [metadata isolation](../CONTEXT.md#blockwise-dsa-metadata-family) [replacement DSA receive](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L928)

**Risk**: PR 在 2026-08-28 仍为 open，无 human `APPROVED` review。当前 head 仍有一个未闭环的 inline review concern：SFA indexer group 在 non-designated port 上没有 replicated blocks、但仍有 regular group blocks 时，会落入 regular mapping；review 指出这可能造成 silent cache corruption 或 transfer crash。现有三个新增测试没有覆盖这个组合，因此 backport 前应先把它写成 failing regression 并决定正确行为。[unresolved review](https://github.com/vllm-project/vllm-ascend/pull/14958#discussion_r3855522694) [current branch at transfer selection](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L957-L970) [current tests](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/tests/ut/kv_offload/test_mooncake_connector.py#L1195-L1243)

## 证据状态

- `confirmed`: GitHub PR/API、official commits/refs、两条本地 source checkout、配套 vLLM checkout、`workspace.lock.json` 和 feature-local contract 的只读证据。
- `inferred`: 从现有 control/data path 推导的 backport 分层、冲突修复范围和 runtime 风险；已明确标出推导依据。
- `not run`: 没有修改源码，没有 cherry-pick，没有执行 pytest、Mooncake transfer、serving、NPU、cache-content correctness 或 performance validation。
- 已执行的本地 check 只有 source/history inspection、ancestry/diff inspection、`git diff --check` 和两条 checkout 上的 `git apply --check --verbose`；apply check 的失败是 direct-integration compatibility evidence，不是 runtime test result。

replacement source 的 compatibility check 可按下列 read-only 命令复现；调查时旧 behavior-reference snapshot 的同类 check 也失败，首提交还因本地没有 `patch_kv_delivery_preemption.py` 而失败：

```bash
git -C repos/vllm-ascend \
  diff 820a21d6593b74211863c7787e1ba9b4deaf9126..upstream/pr-14958 -- \
    vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py \
    tests/ut/kv_offload/test_mooncake_connector.py \
  | git -C repos/vllm-ascend apply --check --verbose
```

## Capture-time source state：两个不同的 source snapshots

调查执行时使用了以下两个 vLLM-Ascend snapshots；2026-08-29 已把 replacement branch 迁到 canonical `repos/vllm-ascend`，旧 behavior-reference checkout 不再是当前工作区状态：

| Identity | Capture-time branch / HEAD | Role | PR patch check |
| --- | --- | --- | --- |
| historical behavior reference | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` / `60eb76e46225e9aaec1493fb247313f8642486ad` | 调查时 canonical path 中的旧 checkout | cumulative patch failed；first PR commit patch failed |
| `repos/vllm-ascend` | `feature/blockwise-dsa-mooncake-v1-reimplementation` / `117637d205603b0c1e43aa0ea3e141de926ff3b1` | published durable source；当前 canonical checkout | cumulative patch failed；first PR commit patch failed |
| `repos/vllm` | `feature/mte_fuised_rebase_0713_mooncake_test-0817-both-pd` / `0fc695fc6d1d82e9a5ac6835ac8e4e1c83703665` | 配套 vLLM v0.23.0 baseline | no source change required by final PR diff |

调查时 `workspace.lock.json` 已记录 replacement `117637d20`，但 canonical checkout 仍是旧 behavior reference；该 mismatch 已于 2026-08-29 通过把 replacement branch checkout 到 `repos/vllm-ascend` 消除。[lock record](../../../workspace.lock.json#L16-L24) [repo-state identity](../repo-state.md#L5-L9) [lock refresh note](../repo-state.md#lock-refresh-note)

调查开始和结束时，两条 source checkout 与 vLLM checkout 都没有 tracked/untracked source changes；control repo 原有未跟踪 `deployment_yaml/` 保持未动。

## PR identity 与 commit topology

截至 capture time，GitHub API 给出的 #14958 状态为：

| Field | Value |
| --- | --- |
| Title | `[Feature][P/D] Support unsymmetrical DCP between prefill and decode` |
| State | open, non-draft, unmerged |
| Base | `releases/v0.26.0rc@d543ccee0a1ff677165777e3defafd42b35e83ef` |
| Head | `lsjfy-open-com/vllm-ascend:releases/v0.26.0rc@1009938d4d10187a4e24fcce4bde72808a016d27` |
| Diff | 2 files, `+75/-16` |
| PR commits | 6 linear commits |
| GitHub mergeability | `mergeable=true`, `mergeable_state=clean` against the PR base |

Source: [official PR API](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14958), [official files API](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14958/files), [official commits API](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14958/commits).

Local official-ref topology inspection found:

```text
merge-base(base, head) = 820a21d6593b74211863c7787e1ba9b4deaf9126
base...head            = 5 commits on base side / 6 commits on head side
```

因此 GitHub 的 `clean` 只说明 PR head 可以与它自己的 v0.26 release base 合并，不说明可以与本地 `60eb76e` 或 `117637d20` 合并。两条本地 source 与 PR head 的 merge-base 都是旧 commit `88c2c87d0c405f4963de2de75ce1f54bf9654046`；live checkout 与 PR head 分别相差 `55/407` 和 `74/407` commits。

### 为什么不能只 cherry-pick 最后一个 commit

| Order | Commit | Actual role |
| --- | --- | --- |
| 1 | [`3d79025d`](https://github.com/vllm-project/vllm-ascend/commit/3d79025d250e400fdf657ebe7be27059e391d76a) | 引入 feature/tests，同时错误地改了两个 spec-stats call sites |
| 2 | [`61f6cbfd`](https://github.com/vllm-project/vllm-ascend/commit/61f6cbfd38b0344e8f43afa1b2263f5b3d93423a) | empty `Trigger CI` commit |
| 3 | [`45dc05d3`](https://github.com/vllm-project/vllm-ascend/commit/45dc05d3963f428fda73ed398c9f2c223bed453f) | 为 `__new__` worker tests 补 `vllm_config` mock |
| 4 | [`1fbc1f09`](https://github.com/vllm-project/vllm-ascend/commit/1fbc1f09799cfc1f918bb5fd76086518dcbc12ca) | 把 v0.26 spec-stats kwarg 改回 `num_draft_tokens` |
| 5 | [`e02e659d`](https://github.com/vllm-project/vllm-ascend/commit/e02e659d9a40e217a74e95538acc02f10a397557) | 中间态：增加 signature inspection compatibility helper |
| 6 | [`1009938d`](https://github.com/vllm-project/vllm-ascend/commit/1009938d4d10187a4e24fcce4bde72808a016d27) | 删除 compatibility helper，恢复 v0.26 contract，并收窄 Mooncake delta |

最终 cumulative diff 对 `vllm_ascend/core/recompute_scheduler.py` 和 `patch_kv_delivery_preemption.py` 为零，只剩 connector 和 connector tests。最后一个 commit 只是相对第 5 个中间态的 cleanup，不包含完整 feature；只 cherry-pick `1009938d` 不会得到 #14958 的最终行为。反过来，逐个 cherry-pick 6 个 commit 会把已经被最终 diff 撤销的 scheduler API 试验带入冲突处理，还会在本地不存在的 `vllm_ascend/patch/platform/patch_kv_delivery_preemption.py` 上立即冲突。

PR body 把 #14958 描述为 #14836 的 v0.26 port；#14836 同样仍是 open/unmerged，目标是 `main`，head 为 `dbbd4960`，包含 2 个 commit。[#14836 API](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14836) [#14836 commits](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14836/commits)

## PR 的真实行为 contract

### Intent

v0.26 base 已经允许 Prefill/Decode 使用不同 CP sizes，但 replicated-indexer transfer 是否启用只看 Decode local `enable_sfa_dcp_replicated_indexer`。这个 helper 只有在 local `decode_context_parallel_size > 1` 时为 true；当 Prefill `DCP > 1`、Decode `DCP = 1` 时，Decode 因此不生成 replicated indexer block mapping，尽管 Prefill 已按 replicated layout 存储 Indexer K。[PR body](https://github.com/vllm-project/vllm-ascend/pull/14958) [helper definition on local baseline](../../../repos/vllm-ascend/vllm_ascend/utils.py#L114-L136)

#14958 把 eligibility 改为：

```python
local_uses_replicated_indexer = self.enable_sfa_dcp_replicated_indexer
remote_uses_replicated_indexer = (
    model_uses_sfa_sparse(self.vllm_config.model_config)
    and meta.remote_dcp_size > 1
)
enabled = local_uses_replicated_indexer or remote_uses_replicated_indexer
```

Source: [PR worker eligibility](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3468-L3478).

这不是任意方向的 asymmetric DCP support。Helper 继续要求 `remote_cp_size % local_cp_size == 0`；PR 的新增 unit case 只覆盖 remote `DCP=2`、local `DCP=1`。因此 confirmed scope 是 Prefill CP 为 Decode CP 的整数倍，尤其 P-on/D-off；`P CP < D CP` 或不可整除组合不在 contract 内。[divisibility check](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3486-L3492) [remote-only test](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/tests/ut/kv_offload/test_mooncake_connector.py#L3710-L3735)

### Data mapping

`_get_sfa_replicate_k_block_ids()` 根据 global prompt block index，把 remote logical block 展开到 `remote_block * remote_cp + remote_rank_offset`，把 local logical block 展开到 `local_block * local_cp + local_rank_offset`；prefix-cache 场景要求 scheduler 提供完整 local block list，而不只是 unhashed suffix。它还要求 request metadata 恰好有一个 logical KV cache group。[mapping implementation](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3480-L3527) [prefix/full-block tests](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/tests/ut/kv_offload/test_mooncake_connector.py#L3664-L3708)

replicated block IDs 只附到选中的第一个 transfer port；receiver 侧在有 replicated blocks 时独立 group contiguous ranges。实际 cache tensor 选择不再靠 local DCP flag 或 `block_size_scale > 1`，而靠 serialized `kv_cache_spec_type == "AscendSFAIndexerCacheSpec"`，以免 regular MLA KV 错用 replicated IDs。[port routing](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3563-L3633) [receiver selection](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L782-L826) [cache-spec selection](https://github.com/vllm-project/vllm-ascend/blob/1009938d4d10187a4e24fcce4bde72808a016d27/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L949-L970)

### Public API

最终 diff 不新增 flag、env var 或 public API，也不改 paired vLLM source。`remote_dcp_size` 已经存在于 request metadata；#14958 只是让 worker 在 local switch 为 false 时也读取它。PR 中间提交改过 speculative stats kwarg，但最终 cumulative diff 已完全撤销该变化。[PR final files](https://api.github.com/repos/vllm-project/vllm-ascend/pulls/14958/files)

配套 upstream vLLM v0.26 commit `d02df748` 的 `Scheduler.make_spec_decoding_stats()` 使用 `num_draft_tokens`；本地 vLLM `0fc695fc` 也使用同一 kwarg，所以 #14958 最终版本不要求本地 vLLM API adapter。[v0.26 scheduler](https://github.com/vllm-project/vllm/blob/d02df748bf9efd99022f1a062597dc3cb3808485/vllm/v1/core/sched/scheduler.py#L1676-L1693) [local v0.23 scheduler](../../../repos/vllm/vllm/v1/core/sched/scheduler.py#L1414-L1438)

## Upstream prerequisites 与本地缺口

Local Git topology 确认 prerequisites 的先后关系为：

```text
c43bc7fa4 (#11647) -> c062a7e9f (#11696) -> d4c8445b0 (#13968)
                    -> 820a21d6 (#14958 merge-base)
```

### Required contract 1：separate cache identity 与 physical allocation

Upstream commit `c43bc7fa4` (#11647) 把原先附着在 `AscendMLAAttentionSpec` 的 Indexer K/scale/replication layout拆成独立 `AscendSFAIndexerCacheSpec`，并同步修改 cache registry、model-runner allocation/binding、SFA attention与 Indexer metadata backend。该 commit涉及 10 个文件、`+708/-360`；它不是一个只为 connector增加 type name 的小 patch。[#11647 commit and diff](https://github.com/vllm-project/vllm-ascend/commit/c43bc7fa4091b6236410a87ea61103da15d71a8a)

PR #14958 后续依赖该 identity把 Indexer transfer group与普通 MLA KV区分开。当前 `117637d20` 没有 `AscendSFAIndexerCacheSpec`；它的 `AscendMLAAttentionSpec` 仍同时包含 `sparse_head_dim`、`sfa_dcp_replicated_indexer_size` 和 packed KV/Indexer cache ratio，ordinary connector序列化的 type因此只会是现有 group spec类型。[current packed layout](../../../repos/vllm-ascend/vllm_ascend/core/kv_cache_interface.py#L218) [current group serialization](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3270)

这形成一个尚未决策的 architecture gate：

| Option | Required implementation | Benefit | Primary risk / proof needed |
| --- | --- | --- | --- |
| A. Backport separated specs | 移植 #11647 的独立 spec、allocation、binding和 attention metadata contract，再适配 target 后续 custom代码 | 与 #11696/#13968/#14958 的 upstream identity一致，能直接使用 type-based selection | 不是窄 connector patch；必须证明 current packed SFA、Blockwise DSA positional layout和已发布模型路径未回归 |
| B. Preserve packed layout | 在 connector physical-transfer metadata中引入显式 `main`/`indexer` semantic role，并把 role稳定映射到 packed tuple component；不允许用 scale、local DCP switch或 layer-name substring作隐式判断 | 缩小 allocation/attention改动面，保留 target当前物理布局 | 目前只是 proposal；必须先证明 packed tuple中的 Indexer能作为独立 transfer element寻址，并为序列化、sender、receiver、multi-port和错误输入建立 fail-closed tests |

Option B 不是把 `AscendMLAAttentionSpec` 字符串替换进 #14958 条件。若无法提供跨 Prefill/Decode 一致且可验证的 physical semantic role，它就不可行，应选择 Option A。

### Required contract 2：replicated-indexer request/block plumbing

Upstream commit `c062a7e9` (#11696) 首次为 ordinary Mooncake P/D path 增加以下完整链条，而 #14958 只修改其中三个判断点：

1. `ReqMeta.local_full_block_ids`，用于 prefix-cache 后恢复完整 local logical block table。
2. scheduler 在 build metadata 时保留 full blocks。
3. worker `_get_sfa_replicate_k_block_ids()` 生成 expanded local/remote Indexer K IDs。
4. `start_load_kv()` 把 replicated IDs 绑定到单一 transfer port。
5. receiver request 增加 `local_block_ids_replicate_k` / `remote_block_ids_replicate_k`。
6. receiver transfer path 根据 replicated IDs 构造 address/length lists。

Source: [#11696 commit](https://github.com/vllm-project/vllm-ascend/commit/c062a7e9fd9a5da377d9b86774ad3bdac9ef913b), [v0.26 prerequisite implementation](https://github.com/vllm-project/vllm-ascend/blob/820a21d6593b74211863c7787e1ba9b4deaf9126/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L112-L129).

两条本地 checkout 都已有 `model_uses_sfa_sparse()` 和 `enable_sfa_dcp_replicated_indexer()` helper，但 ordinary connector 中没有上述 `ReqMeta` field、replicated request fields、worker helper 或 port routing。换言之，本地缺的不是 #14958 的一行 OR condition，而是它要修改的整条 data path。

### Required contract 3：logical group 与 physical SFA layout

Upstream release commit `d4c8445b` (#13968，main PR #13965 的 v0.26 backport) 修复两类 correctness 问题：

- scheduler block IDs 按 logical `kv_cache_group_id` 存储，Mooncake transfer groups 可能把同一 logical group 拆成 SFA/MLA 多组，不能用 transfer-group index 直接索引 request block tables；
- SFA (`scale=8`) 与 MLA (`scale=1`) 不能共享同一个 physical metadata index，否则 MLA 可能读取 SFA scale 并生成 unregistered remote address。

它用 `AscendSFAIndexerCacheSpec` 识别 indexer cache，并把 normal target KV、MTP/Eagle、SFA/indexer 分配到独立 metadata planes。[#13968 commit body and diff](https://github.com/vllm-project/vllm-ascend/commit/d4c8445b039e993214ee3c200557e56e4cb2f399)

当前两条 checkout 已有一部分独立演进的 transfer-group、kernel-block 和 CP geometry 逻辑，但没有 upstream #14958 所假定的完整 physical layout shape。不能把 #14958 hunk 中 `kv_cache_spec_type` 的一处 string check 单独抄入，而不验证 request group index、metadata layer index、local/remote scale 与 selected port 是否仍一一对应。

### vLLM conditions

本地 vLLM v0.23 已提供 `KVCacheBlocks.get_block_ids()`，可以承载 #11696 所需 full-block identity；它也已有 `parallel_config.decode_context_parallel_size` 和当前 vLLM-Ascend helper 所需配置。因此未发现必须修改 vLLM core 才能表达该 backport 的证据。[local `KVCacheBlocks`](../../../repos/vllm/vllm/v1/core/kv_cache_manager.py#L25-L101) [local helper](../../../repos/vllm-ascend/vllm_ascend/utils.py#L114-L136)

但这不等于 v0.26 connector patch 与 v0.23 stack ABI-compatible。PR author 只声明并测试 vLLM v0.26 `d02df748`；#11696 原始实现声明 vLLM v0.24 `85c09e98`。本地 v0.23/custom connector 必须通过自己的 tests 与 runtime evidence建立兼容性，不能借用 upstream CI claim。[#14958 body](https://github.com/vllm-project/vllm-ascend/pull/14958) [#11696 commit](https://github.com/vllm-project/vllm-ascend/commit/c062a7e9fd9a5da377d9b86774ad3bdac9ef913b)

## 两条 checkout 的 integration surface

### `repos/vllm-ascend@60eb76e46`

**Confirmed current code**:

- 普通 connector 已能解析 remote/local CP geometry，并显式要求 `remote_cp % local_cp == 0`；这说明 unequal CP 的 regular KV routing 基础存在。[current CP check](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L2769-L2859)
- `KVCacheRecvingThread._transfer_kv_cache_all_groups()` 只消费 ordinary `local_block_ids` / `remote_block_ids`；没有 replicated block request fields。[current receiver](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L730-L785)
- `MooncakeConnectorWorker.start_load_kv()` 直接从 `_get_kv_split_metadata()` 得到 ordinary blocks；不存在 `_get_sfa_replicate_k_block_ids()`。[current worker load](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3430-L3497)
- Source HEAD 的 standalone Blockwise DSA change 很大，但不是 #14958 依赖的 ordinary replicated-indexer plumbing。

**Confirmed conflicts**:

- 最终 2-file cumulative patch 在 connector import context 和 tests context 均无法 apply。
- 首提交还尝试修改本地不存在的 `vllm_ascend/patch/platform/patch_kv_delivery_preemption.py`；connector 和 tests 同样失败。只有 `recompute_scheduler.py` 的中间 API hunk能以 offset apply，但该 hunk在最终 PR diff中已撤销，不应集成。

### `repos/vllm-ascend@117637d20`

**Confirmed current code**:

- ordinary connector 同样没有 #11696 replicated request/block plumbing，因此 #14958 cumulative patch仍不能 apply。
- cache layout仍是 packed `AscendMLAAttentionSpec`，没有 #11647引入的 `AscendSFAIndexerCacheSpec`；所以 #14958 的 type-based cache selection不能原样实现。
- `dsa_pd_offload=true` 的 Decode receive 使用独立 positional layouts 和 `_execute_dsa_receive()`，并按 Indexer D2D/Main D2RH phase构造 transfer lists；它不消费 PR 的 replicated-K fields。[DSA transfer list](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L755-L858) [DSA receive](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L928-L1010)
- `register_kv_caches()` 对 DSA consumer 有专用 registration/layout branch，ordinary/default V1 仍是另一分支。[registration split](../../../repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py#L3618-L3708)

**Inferred semantic interaction**:

- 在 replacement 上 backport #14958 必须保持 `dsa_pd_offload=false` default V1 行为新增、`dsa_pd_offload=true` positional path不变；不能复用普通 replicated metadata去替换 DSA typed metadata。
- PR scenario 与 DSA topology 表面上都可能出现 Prefill CP/TP 大于 Decode，但两者的数据布局和 request identity contract不同。单独通过 #14958 unit tests不能升级任何 Blockwise DSA support claim。
- 由于 replacement 是 lock-linked published source，若用户选择继续当前 feature，应该从当前 canonical `repos/vllm-ascend@117637d20` 创建新的 integration branch/worktree；如需旧 behavior reference，应以 detached worktree 显式 checkout `60eb76e`。完成 source commit、验证和 push 后再按 workspace 流程刷新 lock/repo-state。本 research 未执行这些 mutation。

## PR head 自身的 unresolved risk

当前 production branch：

```python
if is_sfa_indexer_group and has_replicate_k_blocks:
    use_replicated_ids()
else:
    use_regular_group_ids()
```

而 `start_load_kv()` 只把 replicated IDs 绑定到一个 selected transfer port。对其他 port，`has_replicate_k_blocks` 为 false。Inline review 指出：若这些 port 上 SFA indexer transfer group 的 regular block list 非空，代码会用 regular MLA mapping传输 SFA indexer。当前 tests 分别覆盖：

1. SFA indexer + replicated IDs + regular shard empty；
2. regular MLA + replicated IDs present；
3. remote DCP-on/local DCP-off 的 block-ID calculation。

它们没有覆盖 “SFA indexer + no replicated IDs on this port + regular group blocks nonempty”。因此：

- `confirmed`: review concern 针对的 branch仍存在，且 comment没有 reply/resolution；
- `confirmed`: PR state仍 open、human reviews没有 `APPROVED`；
- `inferred`: 是否在 non-designated port `continue`，要由实际 per-port group routing contract和 regression test决定；本 research不把 bot review直接当作已证实 bug；
- `decision gate`: 在 backport前先增加该 case。若 case证明 branch可达，就必须修复后再集成；若证明不可达，test应固定不可达 invariant并解释数据来源。

PR head 的 completed GitHub check runs大多为 success，包括 pre-commit、CPU selected tests 和多个 hardware-labelled selected-test matrix jobs；一个 coverage upload job为 skipped。API 没有证明这些 selected jobs都执行了本 PR 的三个 named tests，更不构成本地 feature runtime证据。该 CI只属于 upstream v0.26 head evidence，不覆盖本地两个 checkout，也不消除上述缺失 case。[check-runs API](https://api.github.com/repos/vllm-project/vllm-ascend/commits/1009938d4d10187a4e24fcce4bde72808a016d27/check-runs)

## 推荐 integration strategy

### 1. 先固定目标与 mode

1. 以 cross-machine durable feature 为目标时，选择当前 canonical `repos/vllm-ascend@117637d20` replacement 作为 source base，在新 branch/worktree 工作；不要以 historical `60eb76e` snapshot 作为集成基线。
2. 明确目标是 ordinary V1 (`dsa_pd_offload=false`) 还是 Blockwise DSA。只有前者由 #14958 描述；后者需要独立设计，不能以本 PR 作为实现完成证据。
3. 保持配套 vLLM `0fc695fc` 不变，除非 backport测试暴露真实 core API blocker；当前 source evidence没有要求先改 vLLM core。

### 2. 用 contract slices 代替 raw cherry-pick

建议按以下可独立 review 的顺序实现：

1. **Architecture decision**: 在 Option A和 B之间做有源码依据的选择，固定 Indexer physical transfer identity、allocation owner、serialized metadata及 sender/receiver lookup invariant；这一步是后续实现 gate，不是边写边猜。
2. **Cache-identity slice**: Option A完整 backport #11647所需 allocation/binding contract；Option B先实现并独立验证 connector-owned semantic-role adapter。两者都必须保留 unknown/mismatched role的 fail-closed行为。
3. **Foundation slice**: 为 ordinary V1加 `local_full_block_ids`、replicated local/remote IDs、worker mapping、single-port binding和receiver transport；移植 #11696 tests中与这些 contract直接相关的部分。
4. **Layout slice**: 核对当前 custom transfer groups与 #13968 contract，确保 logical `kv_cache_group_id`、physical SFA metadata index、scale/stride/length和 per-port block list一致；不要机械覆盖本地已有的 custom CP/GLM/DSA logic。
5. **#14958 delta**: eligibility使用 local switch OR `(model_uses_sfa_sparse(local model) and remote_dcp_size > 1)`；Indexer cache选择按 Option A的 `AscendSFAIndexerCacheSpec` 或 Option B的显式 semantic role，不能使用 scale或 local DCP switch；保留 `remote_cp % local_cp == 0` fail-closed。
6. **Review-gap slice**: 先写 non-designated-port/SFA/no-replicated-block regression，再决定 skip或证明不可达。
7. **Isolation slice**: 证明 `dsa_pd_offload=true` 的 typed metadata、positional receive和已发布 async/lifecycle tests无行为变化。

每个 slice都应形成新的 signed-off backport commit，commit message引用 upstream PR/commit及本地偏差。不要保留 #14958 的 empty CI commit、已撤销的 spec-stats experiments或把最后一个 cleanup commit伪装成完整 feature。

### 3. 何时才适合真正 cherry-pick

只有当 source先迁移到包含 #11647、#11696、#13968 等 prerequisite的 compatible v0.26 lineage，并且 #14958 已稳定到要采用的 head/merge commit时，才适合把 upstream final/squash commit作为 cherry-pick候选。即便如此，也应先确认 unresolved review case和 paired vLLM identity。当前 workspace不满足这些条件。

## Validation matrix

| Layer | Required case/evidence | Applies to | Current status |
| --- | --- | --- | --- |
| Source identity | branch, HEAD, dirty state, remotes, paired vLLM, selected target vs lock | both checkouts | `confirmed` |
| Patch compatibility | cumulative final diff and first-commit diff apply check | both checkouts | `confirmed failed` |
| Cache identity/allocation | Option A separated-spec allocation/binding，或 Option B explicit role serialization/lookup/fail-closed behavior | ordinary V1 + DSA isolation | `architecture undecided; not run` |
| Static | formatting/lint/type/import checks for changed files | chosen source | `not run` |
| Focused UT | PR three named tests, adapted to local types | ordinary V1 | `not run` |
| Negative UT | remote CP not divisible by local CP; non-SFA model; no external tokens; missing full blocks under prefix hit | ordinary V1 | `not run` |
| Review-gap UT | SFA indexer on non-designated port, `has_replicate=false`, regular blocks nonempty: skip or invariant proof | ordinary V1 | `missing upstream; not run` |
| Mapping UT | P `DCP=2/8`, D `DCP=1`; first/middle/last blocks; partial final block; prefix-cache suffix | ordinary V1 | `not run` |
| Transfer-group UT | one logical group split into SFA/MLA; independent IDs/scales/metadata planes | ordinary V1 | `not run` |
| Connector regression | full `tests/ut/kv_offload/test_mooncake_connector.py` | ordinary V1 | `not run` |
| DSA isolation | default V1 isolation plus DSA metadata/connector/remote-prefill async happy path targets already used by feature | replacement | `not run for this change` |
| CPU/mock integration | P DCP-on metadata -> D DCP-off block mapping through scheduler, worker, receiver, completion | chosen source | `not run` |
| Real Mooncake/NPU correctness | ordinary V1, P DCP-on/D DCP-off, SFA model, cache-content/output oracle, prefix-hit and no-hit | chosen source | `not run` |
| Multi-port/NPU | verify only designated port writes replicated Indexer K; all other ports neither omit required data nor use regular mapping | chosen source | `not run` |
| Existing Blockwise DSA NPU | rerun bounded glm-5.1/glm5.2 cases only if ordinary connector changes share registration/routing code | replacement | `not run for this change` |
| Performance | transfer count/bytes, latency and throughput vs symmetric baseline | chosen source | `not run` |

按照 workspace rules，CPU/mock tests应在 `liangjiahao` namespace 的 dedicated CPU-only UT Pod执行，显式同步 selected checkout并禁用 bytecode/cache；真实 NPU cases必须与 static/CPU evidence分开报告。本 research没有创建或执行 Kubernetes workload。

## 最终判断边界

- `confirmed`: #14958 的最终功能差异很小，但它建立在本地缺失的 #11647、#11696和 #13968 contract之上；两条 checkout都不能直接 apply/cherry-pick。
- `confirmed`: durable target使用 packed `AscendMLAAttentionSpec`，不存在 #14958用于 Indexer identity的 `AscendSFAIndexerCacheSpec`；先选择 full separated-spec backport或 explicit semantic-role adapter是实现 gate。
- `confirmed`: 最终 PR不要求修改 vLLM spec-stats API；本地 v0.23的 `num_draft_tokens`与 PR最终选择一致。
- `confirmed`: PR只覆盖 ordinary Mooncake replicated-indexer path，不实现 Blockwise DSA positional path。
- `confirmed`: upstream CI不能替代本地 backport validation，且 PR仍 open并有一个未闭环的 corruption concern。
- `recommended`: 先用有源码依据的 design review关闭 cache architecture gate；随后在 lock-linked replacement上开独立 integration branch，以 semantic backport slices实现 ordinary V1 feature，并先闭环 review-gap regression；不要逐个 cherry-pick 6 个 PR commits。
- `not run`: 没有任何本地实现、unit test、NPU或performance结果，不能报告 feature已集成或可运行。
