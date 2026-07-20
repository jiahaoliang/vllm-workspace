# Mooncake 按块逐层 KVPool 实施计划

> **供 agent 执行者阅读：** 必须使用子技能
> `superpowers:subagent-driven-development`（推荐）或
> `superpowers:executing-plans`，逐项实施本计划。各步骤使用 checkbox
>（`- [ ]`）语法跟踪进度。

**目标：** 扩展现有 vLLM Ascend 按块逐层 KVPool 流水线，使
`backend=mooncake` 使用 Mooncake Client session 和 range transfer，同时保持现有
memcache、Mooncake whole-key 及其他 backend 的行为不变。

**架构：** 泛化 memcache 参考分支引入的 `KVCacheStoreLayer*Thread` 路径。
Memcache 继续使用 flat-GVA transfer batch；Mooncake 使用 key-major 的
session/range batch，所有远端 descriptor、lease 和 replica 状态均由 Mooncake
Client 持有。

**技术栈：** Python、vLLM v0.24.0、vLLM Ascend、Mooncake Python Client、
NumPy、PyTorch/NPU event、pytest/unittest mock、PowerShell workspace 工具。

## 全局约束

- 从 `repos/vllm-ascend` commit
  `b792c37d7fcf2db05111c3ce84358b1fcde6ad0f` 开始实施，新建个人分支
  `feature/mooncake-layerwise-kv-pool`。
- 使用 `repos/vllm` 的 `v0.24.0` tag（commit
  `ee0da84ab9e04ac7610e28580af62c365e898389`）进行验证。
- 历史 commit `674594c51d6f22c12136e5130ce4c677c9f913ec` 仅作参考；不要
  cherry-pick。
- 本次实施不修改 vLLM attention hook、`MooncakeLayerwiseConnector` 或 Mooncake
  C++/wheel 源码。
- 保持 `repos/Mooncake` 只读；在 contract gate 和 NPU gate 阶段集成 Mooncake
  团队提供的 wheel/commit。
- 当前 Mooncake-side WIP 实现来自 PR #2881：`ascend-direct-dev/Mooncake`
  `feature/layerwise-kv-session`，首次纳入时固定在
  `c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8`。该 PR 是浮动的集成输入，不是稳定
  baseline；更新 head 后必须重新检查 contract 并刷新 workspace 状态。
- Mooncake 和 Memcache block-key layerwise 的首期支持范围为基于 TP 的 MLA 和
  GQA。当 PP、PCP 或 DCP world size 大于 1 时，拒绝启用 block-key layerwise。
- 不为 `enable_ssd_offload` 增加 layerwise 专用限制、覆盖值或默认值；保留现有
  `mooncake.json` setup 路径。
- `use_layerwise=false` 必须保持 whole-key 行为。Yuanrong 及其他非 memcache、
  非 Mooncake backend 必须保持 per-layer-key thread。
- 每个源码 commit 都必须采用 Conventional Commits，并使用 `git commit -s`。
- 每个有意义的源码里程碑 push 后，都要按 workspace 工作流刷新 control repo
  lock 和 feature 状态。
- Task 0 与 control repo 收尾命令从 workspace 根目录运行。Task 1-5 中所有
  `python`、`ruff`、`format.sh` 及 vLLM Ascend 源码 `git` 命令，除非步骤另有说明，
  均从 `repos/vllm-ascend` 运行。

---

## 决策记录

本节记录形成本计划的完整决策过程。若有明确说明，后续决策覆盖先前决策。

### D00：实施归属与范围

**问题：** 交付内容的各个部分分别归属哪个仓库和团队？

**决策：** 本次实施只修改 vLLM Ascend 源码。Client、Transfer、Master 和 wheel
改动由 Mooncake 团队负责。vLLM 源码只读，仅使用兼容的验证 tag。vLLM Ascend
侧负责定义并测试跨团队 API contract，随后集成交付的 wheel，不将 Mooncake
实现复制到本仓库。

### D01：Mooncake API 可用前的开发方式

**问题：** vLLM Ascend 应等待 Mooncake wheel、支持旧路径 fallback，还是并行地按最终
contract 实施？

**决策：** 采用 contract-first 并行开发，并使用严格的 fake Client。当选择 Mooncake
layerwise 时，若缺少 session/range API，必须明确失败。不要 fallback 到旧的
per-layer-key Mooncake 路径。

Mooncake PR #2881 已提供七个 API 的 WIP 实现，因此 vLLM Ascend 开发继续使用 strict
fake 固定 contract，同时用记录的 PR head 构建 wheel 运行真实 contract gate。WIP
实现与 contract 不一致时以本计划的 gate 为准，不在 Backend 中兼容两套语义。

内部 `Backend.batch_commit` / `batch_revoke` 默认返回 `[0] * len(keys)`；Memcache
显式实现相同的 no-op，因为 flat-GVA holes 无需单独发布或撤销 session。Mooncake 覆盖
这两个方法并委托 `batch_put_end` / `batch_put_revoke`。其他不支持的 session/range
method 继续显式抛出 `NotImplementedError`。

**否决的方案：** 运行时 fallback 到旧路径；等 Mooncake 团队完成后再开始 vLLM
Ascend 工作。

### D02：加载失败行为

**问题：** Mooncake layerwise 应强制重计算、始终让请求失败，还是复用标准 vLLM
load-failure policy？

**决策：** 通过 `get_block_ids_with_load_errors()` 报告准确的本地 block ID，并遵循
标准 `kv_load_failure_policy`。文档和 E2E 示例使用
`kv_load_failure_policy="recompute"`。

**影响：** rollback/rescheduling 由 vLLM core 负责。即使失败，AscendStore 也必须
设置 layer event，避免当前 forward 死锁。

### D03：实施基线

**问题：** backport 到旧 v0.20.2rc1 分支、使用当前 b792 分支搭配 vLLM release，
还是使用其已验证的 main commit？

**决策：** 最初从 `b792c37` 实施；协作者分支合入停止支持 v0.23.0 的 main 后，将
验证基线更新为 vLLM v0.24.0 release tag `ee0da84ab`。vLLM 源码保持不变。

### D04：首期并行拓扑

**问题：** 仅支持 TP、扩展 PP/PCP/DCP 的 key schema，还是仅将这些拓扑标记为
未验证？

**决策：** 仅支持基于 TP 的 MLA/GQA。当 PP、PCP 或 DCP 大于 1 时，Mooncake 和
Memcache block-key layerwise 必须快速失败，以防
`{model}@{block}@{head_or_tp_rank}` key schema 发生冲突。

### D06：返回码 contract

**问题：** 将所有非负返回码视为成功、在 backend 中把所有成功码归一化为 0，还是区分
control API 与 data API？

**决策：** Control API（`start`、`commit`、`revoke`、`get_end`）仅接受 `0` 为成功；
正值属于 contract 违例，任何非零值都按失败处理。Mooncake contract 使用负数错误码。
Ranged data API 将所有非负值视为成功、负值视为失败。不要把原始 ranged result
传给现有的 `code != 0` failure helper。

### D07：Layerwise 实施结构

**问题：** 泛化现有 Layer thread、增加 Mooncake 专用 thread，还是模拟 memcache GVA
interface？

**决策：** 泛化现有 `KVCacheStoreLayerSendingThread` 和
`KVCacheStoreLayerRecvingThread`。保留独立的 flat-GVA 与 key-major batch type，
使 backend 差异保持显式。

### D08：Backend 责任边界

**问题：** session 状态、descriptor、lease deadline 和 replica selection 应放在哪里？

**决策：** 这些状态由 Mooncake Client 持有。`MooncakeBackend` 仅做薄委托；Worker
和 transfer thread 只处理 key、已注册的本地 pointer、size、offset、返回码及本地
编排状态。

### D09：Metadata 与跨层状态

**问题：** 失败 key 应修改 shared metadata，还是由 per-batch 状态跟踪？

**决策：** 保持 `SharedBlockData` 只读。session preparation 阶段用 `None` 条目保持
key/block 对齐，构建 shared batch 时再过滤；每个 transfer thread 私有地维护当前
forward batch 的可变 `active_mask`。

### D10：验证与交付

**问题：** 必须通过哪些 gate，commit 应如何拆分？

**决策：** 先运行严格的 fake Client CPU test，再运行真实 wheel contract gate，最后
运行 NPU E2E。源码交付拆分为 backend contract、scheduling、metadata/range
builder、orchestration 和文档里程碑；每个有意义的状态都要 push，并记录到 control
repo。

### D11：SSD offload 策略

**初始决策（已被取代）：** Mooncake layerwise capability validation 时拒绝
`enable_ssd_offload=true`。

**最终决策：** 不增加显式的 layerwise SSD 约束。保留现有 MooncakeBackend 配置路径，
让用户按既有环境启用或禁用 SSD。replica selection 仍由 Mooncake Client 负责；当所选
replica 无法提供 ranged session 时，必须返回负数错误码，AscendStore 按 D02 路由该
失败。

### D12：计划与决策文档布局

**问题：** 将决策保留在计划中、另建 decisions 文件，还是同时维护两者？

**决策：** 只保留一份 feature-local 文档
`features/kv-pool-layerwise-reuse/implementation-plan.md`，其中包含这个独立的
“决策记录”章节。

### D13：Chunked Prefill read-session ownership

**问题：** 多个 chunk 需要反复续约累计 load keys；多个并发请求还可能共享同一个
prefix key。谁维护跨 chunk 状态，何时调用 `batch_get_end`？

**决策：** 由 vLLM Ascend Worker 维护 `req_id -> keys` 和
`key -> active request owners`。每个 chunk 对该请求的累计 load keys 调用
`batch_get_start`；SendingThread 只把 `batch_put_end` 成功的 key 提升为后续 chunk
load key。中间 chunk 不关闭 read session；last chunk、preempt 或 finished cleanup
只移除对应 request owner，并且只有一个 key 的最后 owner 被移除时才调用
`batch_get_end`。Mooncake Client API 不增加 owner/refcount 参数。

---

## 跨团队 API Contract

Mooncake 团队必须在 `MooncakeDistributedStore` 上暴露符合以下 contract 的方法：

```python
from mooncake.store import ReplicateConfig


class MooncakeLayerwiseStoreContract:
    def batch_put_start(self, keys: list[str], sizes: list[int]) -> list[int]:
        raise NotImplementedError

    def batch_put_from_multi_buffer_ranges(
        self,
        keys: list[str],
        all_buffers: list[list[int]],
        all_sizes: list[list[int]],
        all_dst_offsets: list[list[int]],
        config: ReplicateConfig | None = None,
    ) -> list[int]:
        raise NotImplementedError

    def batch_put_end(self, keys: list[str]) -> list[int]:
        raise NotImplementedError

    def batch_put_revoke(self, keys: list[str]) -> list[int]:
        raise NotImplementedError

    def batch_get_start(self, keys: list[str]) -> list[int]:
        raise NotImplementedError

    def batch_get_into_multi_buffer_ranges(
        self,
        keys: list[str],
        all_buffers: list[list[int]],
        all_sizes: list[list[int]],
        all_src_offsets: list[list[int]],
    ) -> list[int]:
        raise NotImplementedError

    def batch_get_end(self, keys: list[str]) -> int:
        raise NotImplementedError
```

以上 method body 表达的是 interface contract；具体实现归 Mooncake 仓库所有。该
contract 在 signature 和行为层面是完整的：

- 输入采用 key-major 布局，并按 index 对齐。
- offset 是 object-byte offset，不是 layer ID。
- Start/end/revoke 成功时返回 `0`，失败时返回负数错误码；vLLM Ascend 将任何意外的
  control 正值结果视为失败。
- Range call 返回非负成功值或负数错误码。
- Client session 缺失或过期时，range call 绝不查询 Master。
- `batch_put_end` 使 object 可见；PROCESSING object 不算 hit。
- `batch_get_start` 在 Client 内保存 descriptor 和 lease deadline；重复调用会重新查询并
  刷新该 key 的 deadline，用于每 chunk 续约。
- `batch_get_end` 清理 Client read session。
- 现有 Mooncake SSD setup 保持不变。replica placement 与 ranged support 由 Client
  和部署配置决定。

当前实现来源：Mooncake PR #2881，captured head
`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`。该 head 将旧
`c1d5bf1f12b9c44a3d12601ab2fac94dd4fcc3a8` 的五个 feature commits squash 为一个
commit，两个 head 的 source tree 完全一致。该 WIP head 已暴露上述七个方法，但当前
测试仍将第二次 `batch_put_end` 视为 `INVALID_PARAMS`，且 Python binding 的
`batch_put_from_multi_buffer_ranges` 仍未暴露 contract 中的可选 `config` 参数。Task 5
仍要求 put-end 幂等和完整 signature；PR 行为与最终 contract 对齐前不得通过
real-wheel gate。

## 计划中的文件职责

- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/backend.py`:
  内部 Backend contract；commit/revoke 默认成功，其他不支持的 session/range method
  显式抛出 `NotImplementedError`。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`:
  capability check 与 Mooncake Client 薄委托。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/memcache_backend.py`:
  保持既有 flat-GVA alloc/copy/lease 行为，并显式实现 commit/revoke no-op。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`:
  block-key helper 与 Mooncake range metadata type。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`:
  backend-specific block-key hit check。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`:
  topology validation、session preparation、load session 收尾与跨 step put tracker。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py`:
  Worker 内部的 chunk-spanning request/key registry、put commit promotion 与共享 key
  owner release。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`:
  range-batch 构建与 per-layer transfer 状态机。
- `repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py`:
  重命名后的 block-key gate，public hook contract 保持不变。
- `repos/vllm-ascend/tests/ut/distributed/ascend_store/`:
  严格的 fake Client、unit test 与 regression coverage。
- `repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md`:
  Mooncake 用法与部署约束。

## Feature 状态检查点矩阵

每个检查点都要用 `git -C repos/vllm-ascend rev-parse HEAD` 获取准确的源码 SHA。
`workspace.lock.json` 和 `repo-state.md` 由 `lock-repos.ps1` 生成；验证并提交
control repo 前，按下表对应行准确编辑 `status.md` 和 `sync-log.md`。

| 检查点 | `status.md` 当前阶段 | `status.md` 下一步 | `sync-log.md` 条目 |
|---|---|---|---|
| Task 0 基线 | `implementation baseline` | `Implement the Mooncake layerwise Backend contract.` | 记录 vLLM v0.24.0 SHA，以及新的 vLLM Ascend branch/base SHA。 |
| Task 1 Backend | `backend contract implemented` | `Generalize block-key scheduling for Mooncake.` | 记录已 push 的 Backend contract SHA 和七个已冻结的 Client method。 |
| Task 2 Scheduler | `block-key scheduling implemented` | `Add key-major request metadata and range batches.` | 记录已 push 的 gate/key/Scheduler SHA 和仅支持 TP 的边界。 |
| Task 3 Metadata | `range metadata implemented` | `Implement Mooncake session orchestration and cleanup.` | 记录已 push 的 metadata/Builder SHA 和 key-major offset contract。 |
| Task 4 Orchestration | `source implementation complete` | `Integrate the Mooncake wheel and run contract/NPU gates.` | 记录已 push 的 session orchestration SHA，以及已完成的 CPU test 命令和结果。 |
| Task 5 最终状态 | `integration validated` | `Prepare upstream review and performance follow-up.` | 记录源码 SHA、Mooncake wheel version/commit、contract 结果、NPU model/config、SSD 设置、准确性结果和重计算结果。 |

---

### Task 0：发布计划并记录兼容的开发基线

**文件：**

- 修改：`workspace.lock.json`
- 修改：`features/kv-pool-layerwise-reuse/repo-state.md`
- 修改：`features/kv-pool-layerwise-reuse/status.md`
- 修改：`features/kv-pool-layerwise-reuse/sync-log.md`
- 新建：`features/kv-pool-layerwise-reuse/implementation-plan.md`

**接口：**

- 输入：干净的 control repo `kv-pool-layerwise-reuse` 分支和干净的各独立源码仓库。
- 输出：vLLM v0.24.0 checkout 和个人 vLLM Ascend feature branch。

- [ ] **步骤 1：确认计划是 control repo 的唯一改动，且源码仓库均为干净状态**

```powershell
git status --short --branch
git -C repos/vllm status --short --branch
git -C repos/vllm-ascend status --short --branch
git -C repos/Mooncake status --short --branch
git -C repos/vllm-ascend remote -v
git -C repos/Mooncake remote -v
.\scripts\status-all.ps1
```

预期：control repo 只报告
`features/kv-pool-layerwise-reuse/implementation-plan.md`；所有源码仓库均为干净
状态；vLLM Ascend 位于 `b792c37`；remote 符合 workspace feature 规则。

- [ ] **步骤 2：在更改 checkout 前提交并 push 已批准的计划**

```powershell
git add features/kv-pool-layerwise-reuse/implementation-plan.md
git commit -s -m "docs: add Mooncake layerwise implementation plan"
git push origin kv-pool-layerwise-reuse
```

预期：实施开始前，control repo 为干净状态，且可从 feature branch fetch 到该计划。

- [ ] **步骤 3：创建实施分支并对齐 vLLM**

```powershell
git -C repos/vllm-ascend switch -c feature/mooncake-layerwise-kv-pool b792c37d7fcf2db05111c3ce84358b1fcde6ad0f
git -C repos/vllm switch --detach v0.24.0
git -C repos/vllm rev-parse HEAD
```

预期：vLLM 报告 `ee0da84ab9e04ac7610e28580af62c365e898389`；vLLM
Ascend 报告分支 `feature/mooncake-layerwise-kv-pool`。

- [ ] **步骤 4：刷新自动生成的 workspace 记录**

```powershell
.\scripts\lock-repos.ps1
$sourceCommit = git -C repos/vllm-ascend rev-parse HEAD
```

预期：lock/repo-state 记录 vLLM v0.24.0 和
`feature/mooncake-layerwise-kv-pool@$sourceCommit`。

- [ ] **步骤 5：应用 Task 0 的 feature 状态行**

在 `status.md` 中设置 `Current Phase: implementation baseline`，将下一步设为
`Implement the Mooncake layerwise Backend contract.`。按 Feature 状态检查点矩阵的
要求，在 `sync-log.md` 追加带日期的条目，其中包含准确的 vLLM v0.24.0 SHA、分支名和
`$sourceCommit`。

- [ ] **步骤 6：验证、提交并 push 基线记录**

```powershell
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
git add workspace.lock.json features/kv-pool-layerwise-reuse/repo-state.md features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md
git commit -s -m "chore: align Mooncake layerwise development baseline"
git push origin kv-pool-layerwise-reuse
```

### Task 1：定义并测试 Backend Contract

**文件：**

- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/backend.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/memcache_backend.py`
- 修改：`repos/vllm-ascend/tests/ut/distributed/ascend_store/_mock_deps.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_backend.py`

**接口：**

- 输入：上文的跨团队 API Contract。
- 输出：`BatchResultShapeError`、`require_aligned_batch_results`、
  `Backend.validate_layerwise_support`, `batch_commit`,
  `batch_revoke`、`batch_put_start`、`batch_get_start`、`batch_get_end`、
  `batch_copy_put` 和 `batch_copy_get`。

- [ ] **步骤 1：添加预期失败的委托与 capability 测试**

添加具有显式 fake method 的测试，并采用等价于以下内容的 assertion：

```python
def test_mooncake_layerwise_methods_delegate(self):
    backend = self._make_backend()
    backend.store.batch_put_start.return_value = [0]
    backend.store.batch_get_start.return_value = [0]
    backend.store.batch_put_from_multi_buffer_ranges.return_value = [64]
    backend.store.batch_get_into_multi_buffer_ranges.return_value = [64]
    backend.store.batch_put_end.return_value = [0]
    backend.store.batch_put_revoke.return_value = [0]
    backend.store.batch_get_end.return_value = 0

    self.assertEqual(backend.batch_put_start(["k"], [64]), [0])
    self.assertEqual(backend.batch_get_start(["k"]), [0])
    self.assertEqual(backend.batch_copy_put(["k"], [[100]], [[64]], [[0]]), [64])
    self.assertEqual(backend.batch_copy_get(["k"], [[200]], [[64]], [[0]]), [64])
    self.assertEqual(backend.batch_commit(["k"]), [0])
    self.assertEqual(backend.batch_revoke(["k"]), [0])
    self.assertEqual(backend.batch_get_end(["k"]), 0)
```

还要测试：缺少 Client method 时抛出 `RuntimeError` 并列出缺失名称；
`enable_ssd_offload=True` 不会导致 capability validation 失败，且仍会进入现有 setup
kwargs 路径。为长度准确、结果过短、结果过长、`None`、Python/NumPy float、numeric
string 和 bool 添加 shape test；只有 Python/NumPy integral（不含 bool）可通过。

- [ ] **步骤 2：运行聚焦测试并确认其失败**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_backend.py
```

预期：由于新的 Backend method 尚不存在，测试失败。

- [ ] **步骤 3：添加准确的 Backend interface**

添加一个共享的 result-shape guard 和以下 Backend method：

```python
from collections.abc import Iterable
from numbers import Integral


class BatchResultShapeError(RuntimeError):
    pass


def require_aligned_batch_results(
    operation: str,
    keys: list[str],
    results: Iterable[int] | None,
) -> list[int]:
    raw_values = list(results) if results is not None else []
    if any(
        isinstance(value, bool) or not isinstance(value, Integral)
        for value in raw_values
    ):
        raise BatchResultShapeError(
            f"{operation} returned non-integer batch results"
        )
    values = [int(value) for value in raw_values]
    if len(values) != len(keys):
        raise BatchResultShapeError(
            f"{operation} returned {len(values)} results for {len(keys)} keys"
        )
    return values


def validate_layerwise_support(self) -> None:
    return None

def batch_commit(self, keys: list[str]) -> list[int]:
    return [0] * len(keys)

def batch_revoke(self, keys: list[str]) -> list[int]:
    return [0] * len(keys)

def batch_put_start(self, keys: list[str], sizes: list[int]) -> list[int]:
    raise NotImplementedError(f"{type(self).__name__} does not support batch_put_start")

def batch_get_start(self, keys: list[str]) -> list[int]:
    raise NotImplementedError(f"{type(self).__name__} does not support batch_get_start")

def batch_get_end(self, keys: list[str]) -> int:
    raise NotImplementedError(f"{type(self).__name__} does not support batch_get_end")

def batch_copy_put(
    self,
    keys: list[str],
    all_buffers: list[list[int]],
    all_sizes: list[list[int]],
    all_dst_offsets: list[list[int]],
) -> list[int]:
    raise NotImplementedError(f"{type(self).__name__} does not support batch_copy_put")

def batch_copy_get(
    self,
    keys: list[str],
    all_buffers: list[list[int]],
    all_sizes: list[list[int]],
    all_src_offsets: list[list[int]],
) -> list[int]:
    raise NotImplementedError(f"{type(self).__name__} does not support batch_copy_get")
```

- [ ] **步骤 4：实现 Mooncake 薄委托与 capability validation**

使用一个常量 tuple 保存必需的 Client method 名称。验证必须调用
`_ensure_initialized()`、检查 `self.store`，并抛出一个包含全部缺失名称的错误。不得
检查或拒绝 `enable_ssd_offload`。

Backend 名称按下表映射到 Client 名称：

| Backend 方法 | Mooncake Client 方法 |
|---|---|
| `batch_commit` | `batch_put_end` |
| `batch_revoke` | `batch_put_revoke` |
| `batch_copy_put` | `batch_put_from_multi_buffer_ranges` |
| `batch_copy_get` | `batch_get_into_multi_buffer_ranges` |
| 其他 session method | 同名 |

- [ ] **步骤 5：运行 Backend 测试并提交**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_backend.py
git add vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend tests/ut/distributed/ascend_store/_mock_deps.py tests/ut/distributed/ascend_store/test_backend.py
git commit -s -m "feat(kv_pool): define Mooncake layerwise backend contract"
git push -u origin feature/mooncake-layerwise-kv-pool
```

预期：Backend 测试通过，feature branch 跟踪个人 fork。

- [ ] **步骤 6：在 control repo 中记录 Backend 里程碑**

在 `repos/vllm-ascend` 中获取 `$sourceCommit = git rev-parse HEAD`，返回 workspace
根目录，并应用 Feature 状态检查点矩阵中的 Task 1 Backend 行。`sync-log.md` 条目必须
列出全部七个已冻结的 Client method 和 `$sourceCommit`。

```powershell
$sourceCommit = git rev-parse HEAD
Set-Location ..\..
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
git add workspace.lock.json features/kv-pool-layerwise-reuse/repo-state.md features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md
git commit -s -m "chore: record Mooncake backend contract state"
git push origin kv-pool-layerwise-reuse
Set-Location repos\vllm-ascend
```

### Task 2：泛化 Block-Key Gate 与 Scheduler Hit 路径

**文件：**

- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/ascend_store_connector.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_scheduler.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_ascend_store_connector.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_scheduler.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_worker.py`

**接口：**

- 输入：Task 1 的 Backend capability API。
- 输出：贯穿 connector、scheduler 和 worker 的 `make_layerwise_block_key` 与
  `use_block_key_layerwise`。

- [ ] **步骤 1：添加预期失败的 gate 与 key 测试**

覆盖下表：

| `use_layerwise` | backend | 预期 thread family |
|---|---|---|
| false | 任意 | whole-key 路径 |
| true | memcache | `KVCacheStoreLayer*Thread` |
| true | mooncake | `KVCacheStoreLayer*Thread` |
| true | yuanrong | `KVCacheStoreKeyLayer*Thread` |

为 MLA 和 GQA 添加准确的 key assertion：

```python
self.assertEqual(make_layerwise_block_key("model", "abc", 0), "model@abc@0")
self.assertEqual(
    make_layerwise_block_key("model", "req_lastblock", 3),
    "model@req_lastblock@3",
)
```

添加 Mooncake scheduler 测试，证明每个 saving-rank key 都必须返回 `1`；遇到
PROCESSING/miss 状态时在该 block 截断；result length 不匹配时抛出 contract error。

- [ ] **步骤 2：运行聚焦的 scheduler 测试并确认失败**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_ascend_store_connector.py tests/ut/distributed/ascend_store/test_pool_scheduler.py tests/ut/distributed/ascend_store/test_pool_worker.py
```

预期：Mooncake 仍选择 KeyLayer thread，并使用 per-layer lookup。

- [ ] **步骤 3：添加规范 key helper 并重命名 gate**

```python
def make_layerwise_block_key(
    model_name: str,
    block_hash_or_tail: str,
    head_or_tp_rank: int,
) -> str:
    return f"{model_name}@{block_hash_or_tail}@{head_or_tp_rank}"
```

将 `use_block_key_layerwise` 定义为：`use_layerwise` 为真，且 backend 属于
`{"memcache", "mooncake"}`。从 connector、scheduler、worker、注释、日志和测试中
移除 `use_gva_layerwise`，但不要重命名真正属于 memcache-specific 的 GVA 数据。

- [ ] **步骤 4：实现 scheduler backend 分支逻辑**

将 `_get_layerwise_gva_hit_tokens` 重命名为
`_get_block_key_layerwise_hit_tokens`。为 memcache 和 Mooncake 构造相同的带 rank
后缀 key；memcache 使用 `batch_get_key_info`，Mooncake 使用 `batch_is_exist`。只有
所有 saving-rank result 均为 complete 时才计入该 block。

- [ ] **步骤 5：强制执行首期拓扑边界**

当 backend 属于 `{"memcache", "mooncake"}` 且启用 block-key layerwise 时，若 PP、
PCP 或 DCP size 大于 1，则拒绝启动；错误消息应列出 backend、不支持的维度及其配置值。
注释必须说明规范 block key 没有编码 PP/PCP/DCP 坐标。不要将此新检查应用于旧
Mooncake whole-key、Yuanrong 或其他非 block-key 路径。vLLM v0.24.0 的
`ParallelConfig` 已保证三个 size 字段存在且为正整数；直接读取字段，不使用
`getattr(..., 1)` 或类型判断把异常配置静默当作 size 1。

- [ ] **步骤 6：运行测试并提交**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_ascend_store_connector.py tests/ut/distributed/ascend_store/test_pool_scheduler.py tests/ut/distributed/ascend_store/test_pool_worker.py
git add vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store tests/ut/distributed/ascend_store
git commit -s -m "refactor(kv_pool): generalize block-key layerwise scheduling"
git push
```

- [ ] **步骤 7：在 control repo 中记录 Scheduler 里程碑**

应用 Feature 状态检查点矩阵中的 Task 2 Scheduler 行。记录准确的源码 SHA、规范 key
格式和仅支持 TP 的边界。

```powershell
$sourceCommit = git rev-parse HEAD
Set-Location ..\..
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
git add workspace.lock.json features/kv-pool-layerwise-reuse/repo-state.md features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md
git commit -s -m "chore: record block-key scheduler state"
git push origin kv-pool-layerwise-reuse
Set-Location repos\vllm-ascend
```

### Task 3：添加 Key-Major Metadata 与 Range-Batch 构建

**文件：**

- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_config_data.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`

**接口：**

- 输入：Task 2 的规范 block key。
- 输出：对齐的 `ReqMeta` key field、扩展后的 `SharedBlockData` 和
  `LayerRangeReqMeta`。

- [ ] **步骤 1：添加预期失败的 metadata 与 offset 测试**

测试两个 block、每层两个 cache segment，并至少覆盖两层。当
`page_size_bytes=96`、segment length 为 `[64, 32]`、layer 为 2 时，assert offset
为 `[[192, 256], [192, 256]]`、嵌套 buffer shape 为 `[2][2]`，且每个 key 对应一个
本地 block ID。加入一个值为 `None` 的中间 key，并 assert 其 key、block ID、buffer、
size 和 offset 会被一起移除。

- [ ] **步骤 2：运行测试并确认失败**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_config_data.py tests/ut/distributed/ascend_store/test_kv_transfer.py
```

预期：当前 metadata 依赖 flat GVA，无法生成 key-major range。

- [ ] **步骤 3：添加准确的 request-key field 与 range-batch type**

向 `ReqMeta` 添加以下 constructor parameter 和 attribute：

```python
save_block_keys: list[str | None] | None = None
save_key_block_offset: int = 0
save_last_block_key: str | None = None
load_block_keys: list[str | None] | None = None
load_key_block_offset: int = 0
load_last_block_key: str | None = None
load_keys: list[str] | None = None
```

`save_block_keys` 和 `load_block_keys` 覆盖从各自 offset 开始的 full block。partial
block 使用对应的 last-block field。在 `ReqMeta.__init__` 内将可选 list input
归一化为新容器，确保不同请求绝不共享 mutable default。

添加包含以下 field 的 batch dataclass：

```python
@dataclass
class LayerRangeReqMeta:
    req_ids: list[str]
    layer_id: int
    block_ids: list[int]
    keys: list[str]
    all_buffers: list[list[int]]
    all_sizes: list[list[int]]
    all_offsets: list[list[int]]
    load_keys: list[str] = field(default_factory=list)

@dataclass
class SharedBlockData:
    block_ids_arr: np.ndarray
    block_gvas_arr: np.ndarray | None
    block_keys: list[str] | None
    req_ids: list[str]
    is_last_chunks: list[bool | None]
    load_keys: list[str] = field(default_factory=list)
```

扩展 `ReqMeta`，加入分别对齐的 save/load key list、offset 和 last-block key。
session-start 失败项保持为 `None`，直到构建 shared batch 时将其与对应本地 block ID
一起过滤。

- [ ] **步骤 4：拆分 flat-GVA 与 key-major 构建输出**

保留现有 memcache address/GVA 计算。对于 Mooncake，每个 key 的本地 pointer 按
`layer_base_addr[j] + block_id * block_stride[j]` 构建，offset 按
`layer_id * page_size_bytes + layer_inner_offset[j]` 构建。不要展开 key-major
嵌套 list。

- [ ] **步骤 5：运行测试并提交**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_config_data.py tests/ut/distributed/ascend_store/test_kv_transfer.py
git add vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/config_data.py vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py tests/ut/distributed/ascend_store/test_config_data.py tests/ut/distributed/ascend_store/test_kv_transfer.py
git commit -s -m "refactor(kv_pool): add key-major layer transfer batches"
git push
```

- [ ] **步骤 6：在 control repo 中记录 metadata 里程碑**

应用 Feature 状态检查点矩阵中的 Task 3 Metadata 行。记录准确的源码 SHA 和
key-major object-offset contract。

```powershell
$sourceCommit = git rev-parse HEAD
Set-Location ..\..
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
git add workspace.lock.json features/kv-pool-layerwise-reuse/repo-state.md features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md
git commit -s -m "chore: record range metadata state"
git push origin kv-pool-layerwise-reuse
Set-Location repos\vllm-ascend
```

### Task 4：编排 Mooncake Session 与 Per-Key 失败处理

**文件：**

- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_worker.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`

**接口：**

- 输入：Task 1 的 Backend method 和 Task 3 的 key-major metadata。
- 输出：跨 step write session、per-forward active mask、write finalization、
  Worker-owned load session 收尾以及标准的 invalid-block 报告。

- [ ] **步骤 1：用预期失败的真实测试替换被 skip 的 Layer-thread 测试**

移除 Layer sending/receiving 测试上的两个整类 skip，并用 `LayerTransferTask` 替换已
弃用的 `LayerMultiBlockReqMeta` input。覆盖以下场景：

- put/get start 部分失败时仍保持稳定的 key/block 对齐；
- 正数 ranged 返回值视为成功；
- 单个 write 失败只 revoke 对应 key，并在后续 layer 中将其过滤；
- 最终 commit 包含全部 active key；
- get-start 与 ranged-read 失败映射到准确的本地 block ID；
- 每个 `list[int]` API 返回过短、过长或非整数结果时，中止整个受影响 batch，且不能
  静默丢弃任何 key；
- Worker 在 last chunk 最终 layer 完成、preempt/finished 或 data abort 路径中释放
  request owner；同一 key 只在最后 owner 释放时执行 `batch_get_end`；
- 中间 layer 抛出异常时，Worker 关闭当前 active owner 并保留 desired keys 供后续 chunk
  重试，RecvingThread 不直接关闭 session；
- commit 成功、commit 失败后 revoke、显式 revoke 后，`_put_started_keys` 内容必须
  准确；
- handler 抛出异常后仍调用 `task_done()` 并设置 layer event。

- [ ] **步骤 2：运行 Worker/transfer 测试并确认失败**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_pool_worker.py tests/ut/distributed/ascend_store/test_kv_transfer.py
```

预期：Mooncake 尚无 session preparation 或 ranged thread 分支。

- [ ] **步骤 3：添加 Worker session preparation**

保持 memcache 的 `_alloc_gvas_for_save` 和 `_prepare_load_gvas` 为
backend-specific。添加执行以下操作的 Mooncake preparation method：

1. 生成带 rank 后缀的 full key 和 last-block key。
2. 在 lock 保护下，对已存在于 `_put_started_keys` 的 key 跳过 `batch_put_start`。
3. 只对新 key 调用 `batch_put_start`，且仅加入 `rc == 0` 的结果。
4. 调用 `batch_get_start`，仅保留 `rc == 0` 的 session，并立即将失败 key 对应的
   本地 block ID 加入 `_invalid_block_ids`。
5. 保留成功打开的 `load_keys`，供 Worker 在最终 layer 或异常中止时统一收尾。

每个 list result 都必须经过 `require_aligned_batch_results`。若 put-start shape
validation 失败，best-effort revoke 所有请求的 key，且不向 `_put_started_keys` 或
shared metadata 加入任何 key。若 get-start shape validation 失败，best-effort end
所有请求的 key，将所有对应本地 block 标记为 invalid，且不向 shared batch 加入任何
read key。

在 buffer 注册完成后、Layer thread 启动前调用 `validate_layerwise_support()`。该验证
不得根据 SSD 配置走不同分支。

- [ ] **步骤 4：实现 SendingThread active 状态**

新 shared batch 的第一层到达时初始化私有 active mask。调用 `batch_copy_put` 前只选择
active key。每遇到一个负数 ranged result，都为该 key 调用 `batch_revoke`、清除其
mask，并在尝试 control call 后从 `_put_started_keys` 移除。

若 ranged-write result shape validation 失败，将所有 active key 视为失败，
best-effort revoke 完整 active set、清除全部 mask，并从 `_put_started_keys` 移除这些
key。

在最终 layer：

1. Commit 全部 active key。
2. 对 commit 失败项执行 best-effort revoke。
3. 设置最终 save event 前清除当前 active 状态。

copy、commit 和 revoke list result 都必须经过 `require_aligned_batch_results`。
commit/revoke shape error 遵循与异常相同的本地清理规则，绝不对未经验证的 result
list 使用 `zip`。

finalization 后的 tracker invariant 必须准确：移除 commit-success key；对
commit-failure key best-effort revoke 后移除；显式 range-failure key 在尝试 revoke 后
移除。格式错误的 commit/revoke result 记为 protocol failure，但仍要在本地移除所有已
尝试的 key，避免 tracker 永久抑制后续 put-start；control call 未关闭的任何远端
session 由 Master timeout 处理。

- [ ] **步骤 5：实现 RecvingThread 失败报告与 Worker 会话收尾**

将 Worker 的 `_invalid_block_ids` set 和 lock 传给 Layer receiver。将 `rc >= 0`
视为 ranged 成功，将 `rc < 0` 视为失败。停止为失败 key 发起后续 layer read；
RecvingThread 只负责 ranged read、invalid block 上报和 layer event，不调用
`batch_get_end`。

Worker 使用 `MooncakeSessionTracker` 跨 chunk 跟踪 request 的 desired load keys、pending
put owner 和 active get owner。正常中间 chunk 只续约不 end；last chunk、preempt/finished
和 abort 通过统一 request-release helper 移除 owner，helper 只把 owner 集合变空的 key
交给 `batch_get_end`。若 ranged-read shape 不匹配，RecvingThread 将所有 active block
标记为 invalid 并通知 Worker 中止 batch；Worker 释放当前 active owner，但保留 desired
keys 供后续 chunk 重新 `batch_get_start`。

若 Mooncake 部署使用 SSD，而 Client 无法为所选 replica 提供 ranged session，则以相同
方式处理其负数错误码；此状态机不要读取 `enable_ssd_offload`。

- [ ] **步骤 6：确保所有 layer handler 都能安全完成**

封装 subclass request handling，确保每个出队 item 恰好调用一次
`request_queue.task_done()`，且当前每层的 finished event 都在 `finally` 中设置。发生
意外 load exception 时，在释放 layer event 前将剩余所有 active 本地 block 标记为
invalid。

- [ ] **步骤 7：运行聚焦测试和完整 AscendStore 测试，然后提交**

```bash
python -m pytest -q tests/ut/distributed/ascend_store/test_pool_worker.py tests/ut/distributed/ascend_store/test_kv_transfer.py
python -m pytest -q tests/ut/distributed/ascend_store
git add vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py tests/ut/distributed/ascend_store/test_pool_worker.py tests/ut/distributed/ascend_store/test_kv_transfer.py
git commit -s -m "feat(kv_pool): orchestrate Mooncake layerwise sessions"
git push
```

预期：所有 AscendStore UT 均通过，且没有关键 Layer lifecycle 测试仍处于 skip 状态。

- [ ] **步骤 8：在 control repo 中记录 orchestration 里程碑**

应用 Feature 状态检查点矩阵中的 Task 4 Orchestration 行。记录准确的源码 SHA、完整的
AscendStore pytest 命令、pass/fail 数量和执行环境。

```powershell
$sourceCommit = git rev-parse HEAD
Set-Location ..\..
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
git add workspace.lock.json features/kv-pool-layerwise-reuse/repo-state.md features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md
git commit -s -m "chore: record Mooncake session orchestration state"
git push origin kv-pool-layerwise-reuse
Set-Location repos\vllm-ascend
```

### Task 5：编写文档、验证并集成 Mooncake Wheel

**文件：**

- 修改：`repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md`
- 修改：`features/kv-pool-layerwise-reuse/status.md`
- 修改：`features/kv-pool-layerwise-reuse/sync-log.md`
- 修改：`features/kv-pool-layerwise-reuse/repo-state.md`
- 修改：`workspace.lock.json`

**接口：**

- 输入：已完成的源码实现和 Mooncake 团队提供的 wheel/commit。
- 输出：面向用户的配置、contract 证据、NPU 证据和可复现的 workspace 状态。

- [ ] **步骤 1：更新 vLLM Ascend 用户指南**

记录以下配置形式：

```json
{
  "kv_connector": "AscendStoreConnector",
  "kv_role": "kv_both",
  "kv_load_failure_policy": "recompute",
  "kv_connector_extra_config": {
    "backend": "mooncake",
    "use_layerwise": true,
    "layerwise_prefetch_layers": 1
  }
}
```

说明仅支持 TP、必需的 Client method、object offset 语义、默认 lease-TTL 责任，以及
首期不支持 Mooncake transfer splitting。说明 SSD 仍由现有 Mooncake 配置控制：vLLM
Ascend 既不强制关闭 SSD，也不保证每个 SSD replica 都能提供 ranged transfer。明确
`layerwise_max_transfer_blocks` / `layerwise_max_transfer_bytes` 当前只限制 Memcache
flat-GVA `batch_copy`，不会拆分 Mooncake ranged request。

- [ ] **步骤 2：在标准 Linux 环境中运行 unit 与 static gate**

```bash
python -m pytest -q tests/ut/distributed/ascend_store
ruff check vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store tests/ut/distributed/ascend_store
bash format.sh ci
git diff --check
```

预期：所有命令均以 0 退出；格式改动经 review 并 stage 后，`format.sh ci` 不留下未提交
的格式化改动。

- [ ] **步骤 3：运行 Mooncake wheel contract gate**

使用从已记录 Mooncake PR #2881 head（或经同步日志批准的后续 head）构建的 wheel
验证，并记录 wheel 版本与精确 commit：

1. `batch_put_start` 成功后，PROCESSING object 对 Exist/GetReplica 不可见；同一个 key
   重复 start 返回冲突错误码。
2. `put_start -> ranged writes -> put_end` 在 put-end 前不可见、put-end 后变为 COMPLETE；
   重复 put-end 保持幂等，并清理 Client put session。
3. `put_revoke` 清理 PROCESSING session，并允许同一个 key 后续重新 put-start；
   COMPLETE object 不可 revoke。
4. `batch_get_start` 缓存 descriptor，并按 Client/Master 默认
   `default_kv_lease_ttl` 写入 deadline；`ranged reads` 返回准确 byte，
   `batch_get_end` 清理 Client get session。
5. start 之后，range call 不发起 Master query；过期或缺失的 session 返回负数错误码，
   且不得触发第二次 Master query。
6. `TransferWriteRange` 支持 `size < object_size` 的多段写入，并与整 key put 的
   `validateTransferParams` 校验路径隔离。
7. 目标环境现有 SSD 设置不变地传入 `store.setup`；任何不支持 ranged 操作的 replica
   返回负数错误码，而不是导致进程崩溃。

- [ ] **步骤 4：使用目标环境配置运行 NPU E2E**

分别对一个 MLA 配置和一个 GQA 配置执行 miss -> layerwise save -> COMPLETE ->
prefix hit -> layerwise load。保留环境现有的 Mooncake SSD 选择。将生成输出与
no-offload 基线对比；运行至少三个 prompt chunks，验证默认
`default_kv_lease_ttl` 能覆盖单 chunk onload，并确认后续 chunk 的
`batch_get_start` 会续约累计 keys；再注入一次 renewal/lease 失败以观察 vLLM 重计算。

- [ ] **步骤 5：提交并 push 源码文档**

```bash
git add docs/source/user_guide/feature_guide/layerwise_kv_pool.md
git commit -s -m "docs(kv_pool): document Mooncake layerwise backend"
git push
```

- [ ] **步骤 6：刷新并提交 control repo 最终状态**

验证前，应用 Feature 状态检查点矩阵中的 Task 5 最终状态行。设置
`Current Phase: integration validated`，准确设置矩阵中给出的下一步，并追加带日期的
sync 条目，其中包含源码 SHA、Mooncake wheel version/commit、contract-test 结果、NPU
model/config、实际生效的 SSD 设置、准确性对比和重计算结果。随后刷新生成状态并验证：

```powershell
.\scripts\lock-repos.ps1
.\scripts\status-all.ps1
.\scripts\validate-workspace.ps1
rg -n 'C:\\Use[r]s|Downloa[d]s|l30034[5]96' .
git diff --check
git status --short --branch
```

预期：lock 与源码 HEAD 匹配，workspace 验证通过，feature 文档不包含机器专用路径，且
只有预期的 feature 状态文件被修改。

```powershell
git add workspace.lock.json features/kv-pool-layerwise-reuse/status.md features/kv-pool-layerwise-reuse/sync-log.md features/kv-pool-layerwise-reuse/repo-state.md
git commit -s -m "chore: record Mooncake layerwise implementation state"
git push origin kv-pool-layerwise-reuse
```

### Task 6：支持 Chunked Prefill 的跨 chunk Mooncake Session

**状态：** source implementation complete；真实 Mooncake wheel / NPU E2E pending。

**文件：**

- 新增：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/mooncake_session_tracker.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py`
- 修改：`repos/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py`
- 修改：`repos/vllm-ascend/docs/source/user_guide/feature_guide/layerwise_kv_pool.md`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_mooncake_session_tracker.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_pool_worker.py`
- 测试：`repos/vllm-ascend/tests/ut/distributed/ascend_store/test_kv_transfer.py`

- [x] **步骤 1：建立线程安全的 request/key registry**

记录 request 的累计 load key 与 block index、pending put key owners 和 active get
owners。完整 block key 替换同 block index 的 partial key，避免后续 chunk 对同一 HBM
block 重复 load 两个远端对象。

- [x] **步骤 2：只提升成功 COMPLETE 的前序 chunk key**

Worker 在 `batch_put_start` 成功后记录 pending owner；SendingThread 仅在末层
`batch_commit` 返回 `0` 时将 key 提升到 owner request 的累计 load set。range/commit
失败走 revoke，并从 pending registry 移除。若 request 同时复用已 started 共享 key
并 start 新 key，新 key start 失败只清理新 key，不得移除该 request 对共享 key 的
pending ownership。

- [x] **步骤 3：每个 chunk 续约并构建累计 ranged load**

初始 prefix hit 与此前 COMPLETE key 合并后执行一次去重的 `batch_get_start`。结果按
request/block slot fan-out；后续 chunk 即使 `load_spec=None`，也会从 registry 重建
`load_block_keys` 和 layer load task。

- [x] **步骤 4：按最后 owner 执行 get-end**

中间 chunk 保留 owner。last chunk 在最后 ranged read 完成后释放当前 request；共享 key
仍有其他 owner 时不调用 `batch_get_end`。preempt/finished 删除 request 状态；receiver
abort 关闭当前 active owner，但保留 desired keys 供后续 chunk 重试。

- [x] **步骤 5：完成 CPU unit/static gate**

重写后的源码 commit `8da904ff7048d88aed240645dd1293ca0abdf4ee` 已通过隔离的完整
AscendStore CPU suite（`398 passed`）、Ruff lint、`py_compile` 和
`git diff --check`。新 tracker 与新测试文件通过 Ruff format check；四个既有大文件仍有
本 feature 之前就存在的整文件 format delta，本 Task 不做无关格式化。

- [ ] **步骤 6：完成真实 wheel / NPU Chunked Prefill E2E**

使用至少三个 prompt chunks，验证每 chunk lease renewal、前序 COMPLETE key onload、
本 chunk put-end 可见性、mixed-lastness 共享 prefix ownership 和最终 accuracy。再使用短
lease TTL 注入一次 renewal failure，验证逐 block invalid 与 recompute policy。

## 最终验收标准

- `use_layerwise=true, backend=mooncake` 选择 per-block Layer thread；若已安装的
  Client 缺少必需 API，则明确失败。
- 任何 layerwise-specific 代码都不得拒绝、禁用或重写 `enable_ssd_offload`。
- Scheduler 和 Worker 使用相同的带 rank 后缀 key；PROCESSING object 不算 prefix
  hit。
- `batch_put_start` 和 `batch_get_start` 部分失败时仍保持 key/block/buffer 对齐，且
  不会导致 inference 崩溃。
- 每个返回 list 的 API 在 index 或 zip 前都要检查长度；格式错误的结果会触发整个受
  影响 batch 的清理，不能遗漏任何未报告的 key。
- Per-key ranged write 失败时只 revoke 失败 key；后续 layer 跳过这些 key；最终
  commit 只包含 active key。
- write finalization 后，已 commit 或已尝试 revoke 的 key 都从
  `_put_started_keys` 移除；其他未收尾 PROCESSING session 由 Master timeout 清理。
- 正数 ranged byte count 表示成功；负数 ranged code 映射到准确的本地 invalid block，
  并触发已配置的 vLLM failure policy。
- Worker 每个 chunk 续约 request 的累计 load keys；中间 chunk 不执行
  `batch_get_end`。last/preempt/finished/abort 释放 request owner，同一 key 只在最后一个
  active owner 释放后执行一次 `batch_get_end`；RecvingThread 不拥有 session cleanup，
  transfer exception 不能使 `queue.join()` 或 layer wait 一直阻塞。
- 现有 memcache flat-GVA、Mooncake whole-key、Yuanrong KeyLayer 和 MTP guard 测试
  保持通过。
- 严格的 fake 测试、真实 wheel contract 测试和 NPU E2E 均基于已记录的 commit 与
  目标部署配置通过。
- 真实 wheel contract 证据覆盖 PROCESSING 可见性、重复 start 冲突、put-end 幂等、
  COMPLETE revoke 拒绝、默认 lease TTL、session cache 清理，以及
  `TransferWriteRange` 与整 key 校验路径隔离。
