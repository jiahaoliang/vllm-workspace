Source: https://github.com/ascend-direct-dev/Mooncake/commit/df3f74ed8ebdb0c935554beea6299a9f11c723e2; local `repos/Mooncake` Git graph/reflog; `workspace.lock.json`; current vLLM-Ascend source at https://github.com/jiahaoliang/vllm-ascend/commit/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7
Captured At: 2026-08-07T15:29:46+08:00
Notes: 仅使用 Mooncake 源码/Git history 与当前 vLLM-Ascend 源码进行静态研究。主比较是 workspace 锁定的 `786c77ff7692bed58dd99971afef87d6b690cbe3` 到 collaborator 新 tip `df3f74ed8ebdb0c935554beea6299a9f11c723e2`；`0869a4ae -> df3f74ed` 只作为本次 fetch 的 tracking-ref 证据。未切 branch、未修改 nested repo、未更新 lock，未运行构建、UT、NPU 或 Kubernetes 验证。

# Mooncake collaborator session/range 更新对比

## 结论

1. 这不是 fast-forward。`786c77ff` 与 `df3f74ed` 互不为祖先，merge-base 是 `077e250b55830130997ebb3c84494ec81f178876`，`786c...df3f` 的左右独有提交数是 `3 / 92`。其中新 tip 的父提交 `a6b4db4cfa371a3fc7f189a19977c102e14c4dfc` 比旧公共基点多 91 个 upstream 提交，只有最顶端的 `df3f74ed` 是新版 collaborator feature patch。
2. 七个 Python/C++ public session/range 方法的名称、参数形状和返回形状没有变化；当前 vLLM-Ascend `mooncake_backend.py` 不需要再次改名。wheel project version 也仍是 `0.3.12.post1`。
3. 新 feature 的核心变化是：ranged read/write 改为单次 scatter 聚合；put session 增加 `writable` / `inflight_transfers` 状态并在 end/revoke 前 seal + wait；finalize 只提交 MEMORY replica；对 flexible MEMORY+NoF 做 NoF revoke；拒绝 reliable NoF；Master RPC 或逐 key 失败时保留本地 session 供重试；并修正过滤 key 后的 `group_ids` 对齐。
4. Get session 生命周期和 lease 行为没有实质变化：`batch_get_session_start` 仍查询 Master 并缓存单个 COMPLETE memory replica，ranged get 仍只使用本地 session/lease，`batch_get_session_end` 仍是本地 erase。
5. 正常路径对当前 vLLM-Ascend 静态兼容，但有一个失败路径需要处理：新 Mooncake 在 revoke 暂态失败时故意保留 sealed local session；当前 vLLM-Ascend 只记录错误，然后无条件丢弃自己的 started/session tracker，不会重试。这可能使同一进程后续对同 key 的 `batch_put_session_start` 持续返回 session already exists。
6. 旧 feature patch 对 `ShmHelper` 的 FabricMem 条件曾有一项本地放宽，新 feature patch 将其删除，endpoint 恢复为 `ascend_agent_mode && ascend_use_fabric_mem`。本轮 A2 validation 明确不启用 `ASCEND_ENABLE_USE_FABRIC_MEM`，A3 和专门的 FabricMem/`ShmHelper` mode 不在范围内，因此最终结果不得外推为 FabricMem 已验证。

## 2026-08-07 实施更新

- Mooncake 基线已冻结为 `df3f74ed8ebdb0c935554beea6299a9f11c723e2`，本地 `repos/Mooncake` 保持只读 detached checkout。
- vLLM-Ascend 已在 `45b2e785b10ca4604cd6314819ed15f3ff674781` 实现失败 revoke ownership 保留：writable 与 revoke-pending key 互斥，失败 key 最多重试三次，只有结果 `0` 才释放 pending 和 session tracker。
- CPU-only `liangjiahao/vllm-ascend-ut` 源码门禁通过 `495 passed`，Ruff、`py_compile` 和 `git diff --check` 通过；真实新版 Mooncake wheel、原生 ARM64 镜像和 A2 full validation 结果由 run `20260807T100722Z` 单独记录，不以本静态研究章节替代。

## 版本和提交图

workspace 的机器可读基线是 [`workspace.lock.json:16-35`](../../../../workspace.lock.json)：

| 角色 | SHA / tree | 说明 |
| --- | --- | --- |
| Mooncake 当前 lock/checkout | [`786c77ff7692bed58dd99971afef87d6b690cbe3`](https://github.com/ascend-direct-dev/Mooncake/commit/786c77ff7692bed58dd99971afef87d6b690cbe3), tree `76aaea410e0b33566e9943683f9e2eebd086d379` | merge commit，父提交为 feature `fa4c47b8...` 和当时 upstream `077e250b...` |
| fetch 前 tracking tip | [`0869a4aed4662f3f646a4baf465dbbb06c74ba2a`](https://github.com/ascend-direct-dev/Mooncake/commit/0869a4aed4662f3f646a4baf465dbbb06c74ba2a), tree `76aaea410e0b33566e9943683f9e2eebd086d379` | 单提交重写；tree 与 `786c77ff` 完全相同，`git diff --quiet 786c 0869` 为 0 |
| collaborator 新 tip | [`df3f74ed8ebdb0c935554beea6299a9f11c723e2`](https://github.com/ascend-direct-dev/Mooncake/commit/df3f74ed8ebdb0c935554beea6299a9f11c723e2), tree `50c515ccf3282e7e0e496d3697b45c601c275e17` | 单个新版 feature commit，父提交 `a6b4db4c...` |
| 新 feature 的 upstream 父提交 | [`a6b4db4cfa371a3fc7f189a19977c102e14c4dfc`](https://github.com/kvcache-ai/Mooncake/commit/a6b4db4cfa371a3fc7f189a19977c102e14c4dfc) | 比公共基点 `077e250b...` 多 91 个 upstream commits |
| 当前 vLLM-Ascend | [`6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7`](https://github.com/jiahaoliang/vllm-ascend/commit/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7) | 本报告的 compatibility 检查对象 |

本地 remote reflog `repos/Mooncake/.git/logs/refs/remotes/collaborator/feature/layerwise-kv-session:2-4` 记录了三次 `forced-update`：

```text
74b0acf1 -> 786c77ff
786c77ff -> 0869a4ae
0869a4ae -> df3f74ed
```

因此本次 fetch 显示的 `0869a4ae...df3f74ed forced update` 是 ref 移动证据，但 workspace 实际采用差异必须从 `786c77ff` 开始。提交图核验命令及结果为：

```text
git merge-base 786c77ff df3f74ed
077e250b55830130997ebb3c84494ec81f178876

git rev-list --left-right --count 786c77ff...df3f74ed
3  92

git merge-base --is-ancestor 786c77ff df3f74ed  # exit 1
git merge-base --is-ancestor df3f74ed 786c77ff  # exit 1
```

不能用 endpoint 的全仓库 diff 直接描述 session feature，因为它混入了 91 个 upstream commits。剥离方法是：

- 旧 feature：比较 `077e250b..0869a4ae`；`0869a4ae` 与 workspace lock 的 tree 相同。
- 新 feature：比较 `a6b4db4c..df3f74ed`。
- 旧 patch 为 13 files、`+1710/-30`；新 patch 为 17 files、`+2182/-16`。
- 两个聚合 diff 的 stable patch-id 分别是 `ef9fb60c8ae4716b97f53bcbd4ef15eaaf6eb0c5` 和 `c36fa688405e20f6e1aba11def1eedbacc016cb5`，确认新版不只是 rebase/重写。
- `git range-diff 077e250b..0869a4ae a6b4db4c..df3f74ed` 将两版 feature 配对后显示下述真实语义变化。

## Public API、pybind 和 wheel

新版仍暴露以下七个方法，声明见 [`pyclient.h:299-345`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/include/pyclient.h#L299-L345)，pybind 注册见 [`store_py.cpp:3023-3124`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-integration/store/store_py.cpp#L3023-L3124)：

| 方法 | 返回 | 变化 |
| --- | --- | --- |
| `batch_put_session_start(keys, sizes, config=...)` | per-key `List[int]` | 签名不变；内部新增 config 校验 |
| `batch_put_from_multi_buffer_ranges(keys, buffers, sizes, dst_offsets)` | per-key bytes/error | 签名不变；内部改 scatter 和 inflight tracking |
| `batch_put_session_end(keys)` | per-key `List[int]` | 签名不变；finalize/retry 语义增强 |
| `batch_put_session_revoke(keys)` | per-key `List[int]` | 签名不变；失败时保留 session |
| `batch_get_session_start(keys)` | per-key `List[int]` | 无实质变化 |
| `batch_get_into_multi_buffer_ranges(keys, buffers, sizes, src_offsets)` | per-key bytes/error | 签名不变；底层改 scatter |
| `batch_get_session_end(keys)` | scalar `int` | 无实质变化 |

旧、新两树中上述七个 public declaration block 内容相同；这比只 grep 方法名更强，说明参数顺序、默认 `ReplicateConfig` 和返回类型均未漂移。Python binding 的七个 `.def(...)` 名称和参数转发也未变。

wheel metadata 的 project name/version 仍为 `mooncake-transfer-engine` / `0.3.12.post1`，见 [`mooncake-wheel/pyproject.toml:20-33`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-wheel/pyproject.toml#L20-L33)。`df3f74ed` 自身没有改 CMake、`mooncake-wheel/`、`scripts/build_wheel.sh` 或 CI workflow；session binding 仍由 `store_py.cpp` 进入 wheel。

C++ 内部有一项跟随 upstream 的适配：`Client::BatchPutEnd` 从 key strings 改为 `ObjectMeta`，以配合 upstream 的 optional checksum API；session path 构造 `ObjectMeta{key, std::nullopt}`，明确不计算 checksum，见 [`real_client.cpp:5631-5637`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5631-L5637) 和 upstream commit [`62ca2c23`](https://github.com/kvcache-ai/Mooncake/commit/62ca2c23ab3f8cc0e70742a89d505ffa3f65067f)。这不改变 Python ABI。

## Ranged transfer 数据路径

旧版 `Client::BatchTransferReadRanges` / `BatchTransferWriteRanges` 为每个 entry/fragment 创建多个 `TransferFuture`，最后逐个 wait。新版把所有 entry（write 还包含所有 MEMORY replicas）的 fragment 放入一个 `ScatterRangeBuilder`，只做一次 `submitScatter`，再按 entry 汇总第一个 fragment error 和 logical transferred bytes。实现见 [`client_service.cpp:167-207`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/client_service.cpp#L167-L207)、[`client_service.cpp:3889-4042`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/client_service.cpp#L3889-L4042) 和 [`transfer_task.cpp:1081-1084`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/transfer_task.cpp#L1081-L1084)。

generic scatter API 本身来自新 base 中的 upstream commit [`98e17a2d`](https://github.com/kvcache-ai/Mooncake/commit/98e17a2d7b448db7d1919adc5eb0e73af267c6bb)；`df3f74ed` 的 feature patch 使用它并增加 Ascend Direct 配套行为：

- `AscendDirectTransport::requiresTaskGroupSubmission()` 返回 false，让同一 scatter 的 task groups 一起进入一次 `submitTransferTask`，见 [`ascend_direct_transport.h:50-54`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-transfer-engine/include/transport/ascend_transport/ascend_direct_transport/ascend_direct_transport.h#L50-L54) 和 [`multi_transport.cpp:145-172`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-transfer-engine/src/multi_transport.cpp#L145-L172)。TCP 等默认仍保留 per-task-group submission。
- Default dispatcher 从只按 `segment` 分组改为按 `(segment, opcode)` 分组，避免同一 segment 的 read/write 混合后按第一条 slice 的方向传输，见 [`slice_dispatcher.cpp:65-103`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-transfer-engine/src/transport/ascend_transport/ascend_direct_transport/slice_dispatcher.cpp#L65-L103)。
- RoCE dummy-real dispatcher 相应改为按 `(engine, segment, opcode)` 分组，见 [`slice_dispatcher.cpp:134-164`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-transfer-engine/src/transport/ascend_transport/ascend_direct_transport/slice_dispatcher.cpp#L134-L164)。

这些变化不改变 ranged API 的 key-major 输入/逐 key输出契约，但会直接改变 batch 粒度、Ascend ADXL submission 数和 mixed-op correctness，所以 source-level compatibility 不能替代真实 Ascend 性能/正确性验证。

## Store/session lifecycle

### Get side

旧、新 `batch_get_session_start`、ranged get 和 get end 的实现逻辑逐段相同：

- start 执行一次 `BatchQuery`，校验 lease，选择 COMPLETE memory replica，并覆盖 `get_sessions_[key]`；
- ranged get 不访问 Master，调用前后都检查 cached lease，过期时 erase session 并返回 `LEASE_EXPIRED`；
- get end 只 erase local map，仍返回 scalar 0。

新版固定源码见 [`real_client.cpp:5197-5357`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5197-L5357)。因此 lease refresh、session miss 和 `batch_get_session_end` 的调用方式对当前 adapter 没有新增要求。

### Put side

`PutSessionEntry` 从 `{replicas, object_size}` 扩展为 `{replicas, object_size, write_mode, writable, inflight_transfers}`，并增加 `condition_variable`，见 [`real_client.h:919-934`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/include/real_client.h#L919-L934)。具体行为变化如下：

1. `batch_put_session_start` 先校验 `group_ids.size() == keys.size()`；跳过已有 session 后同步过滤 `group_ids`，避免 `start_keys` 与 routing group 错位。[`real_client.cpp:5360-5427`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5360-L5427)
2. session ranged write 只写 MEMORY replica。`replica_num=1,nof_replica_num=1` 的 flexible dual mode 可进入 session；`replica_num>1` 或 `nof_replica_num>1` 的 reliable mode 若包含 NoF 会在 start 返回 `INVALID_PARAMS`。[`replica.h:150-164`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/include/replica.h#L150-L164) [`real_client.cpp:5379-5390`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5379-L5390)
3. 每个 ranged write 在锁内确认 `writable` 并增加 inflight count；RAII guard 在成功、失败或异常后递减并 notify。end/revoke 先将 session seal 为不可写，再等全部 inflight transfer 退出，消除了 finalize/free 与 range write 的竞态。[`real_client.cpp:5464-5565`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5464-L5565)
4. end 只对 MEMORY 执行 `BatchPutEnd`。flexible dual 若还含 NoF reservation，再单独对 NoF 执行 revoke；reliable NoF 已在 start 被拒绝。[`real_client.cpp:5567-5702`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5567-L5702)
5. 旧版无论 RPC response 数量错误还是逐 key end/revoke error，都会 erase local put session。新版在 RPC shape ambiguity 或逐 key失败时保留 sealed session，让 caller 可以重试 end/revoke；revoke 返回 `OBJECT_NOT_FOUND` 则视为远端已清理并删除本地 session。[`real_client.cpp:5637-5699`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5637-L5699) [`real_client.cpp:5704-5777`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client.cpp#L5704-L5777)

这里的“可重试”是 failure recovery，不是 success 后的 local idempotency：成功 end/revoke 仍删除 local session，第二次调用仍会得到 `INVALID_PARAMS`。

## 另一项 feature 差异：FabricMem ShmHelper 条件回退

旧 feature commit [`347d413f`](https://github.com/ascend-direct-dev/Mooncake/commit/347d413f5a37c86ba6ff9c48ea3478160e37e798) 曾把 `ShmHelper::{allocate,free,cleanup}` 的 VMM 条件从 `ascend_agent_mode && ascend_use_fabric_mem` 放宽为只检查 `ascend_use_fabric_mem`。该 hunk 存在于 workspace 锁定 tree，也解释了旧 feature patch 的 `shm_helper.cpp +17/-24`。

`df3f74ed` 的 17-file feature patch 不再包含 `shm_helper.cpp`；新 endpoint 继承 base 行为，再次同时要求两个 flag，见 [`shm_helper.cpp:48-100`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/shm_helper.cpp#L48-L100) 和 [`shm_helper.cpp:143-160`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/shm_helper.cpp#L143-L160)。这不是 91 个 upstream commits 中对该文件的演进，而是新版 feature 丢弃旧 feature hunk 后的 endpoint 语义差异。

当前 vLLM-Ascend FabricMem setup 通过 `ASCEND_ENABLE_USE_FABRIC_MEM` 选择不注入 TransferEngine 的 RealClient 路径，见 [`mooncake_backend.py:133-160`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py#L133-L160)。Mooncake Python `setup()` 初始化 RealClient，但不设置 agent flag，[`store_py.cpp:2197-2232`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-integration/store/store_py.cpp#L2197-L2232)；`globalConfig().ascend_agent_mode` 默认 false，明确置 true 的路径是 standalone `real_client_main` 或 `DummyClient::setup_dummy`。[`config.h:127-128`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-transfer-engine/include/config.h#L127-L128) [`real_client_main.cpp:112-120`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/real_client_main.cpp#L112-L120) [`dummy_client.cpp:462-481`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/src/dummy_client.cpp#L462-L481)

这并不证明当前 serving 一定触发 `ShmHelper` 分配，也不等价于所有 FabricMem segment 分配都回退；但凡该部署路径实际进入 `ShmHelper`，new tip 会选择 memfd/mmap 而非 VMM。应把 current direct RealClient 和 dummy-real 两种模式都纳入采用前回归，不能只做 method-presence UT。

## 测试变化和缺口

旧 feature 在 `pybind_client_test.cpp` 增加 320 行，已有：正常 multi-key/multi-layer ranges、异常参数/session miss/end 后 miss，以及 get lease expiry。新版 feature 在同文件增加 480 行，保留原测试并新增四组：

- end 失败后 local put session 保留，可重复 end，再 revoke 清理；
- reliable NoF config 在 session start 被拒绝；
- mixed existing/new keys 时 `group_ids` 被正确过滤；
- MEMORY replica end 后状态为 COMPLETE 且可重新 get/read。

新增测试源码见 [`pybind_client_test.cpp:1068-1226`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/tests/pybind_client_test.cpp#L1068-L1226)。TCP E2E 脚本和 Python case 仍在，内容相对旧 feature 无实质变化：[`session_ranges_tcp_e2e.py`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/tests/e2e/session_ranges_tcp_e2e.py)。`client_buffer_test.cpp +3/-3` 是 format-only。

仍未看到直接覆盖以下新行为的 feature tests：

- ranged write 与 end/revoke 的真实并发 race，及 wait/notify 不死锁；
- flexible dual MEMORY+NoF 的 end-MEMORY / revoke-NoF 成功与部分失败矩阵；
- Ascend Direct 单次 scatter 的 submission 数、mixed opcode 分组和吞吐；
- non-agent RealClient + FabricMem 下 `ShmHelper` 的实际 allocator/free 配对；
- vLLM-Ascend revoke 暂态失败后同 key 再 start。

## 91 个 upstream commits 中与构建相关的变化

下面这些属于 `077e250b..a6b4db4c` 的 upstream 同步，不应误写成 collaborator session feature 本身：

- [`622104e4`](https://github.com/kvcache-ai/Mooncake/commit/622104e439b0abac6b253df03ee68bbf45d179f8)：增加 ARM64 non-CUDA release wheels。
- [`7310cddf`](https://github.com/kvcache-ai/Mooncake/commit/7310cddf401517c188018e8417f4cdbd45c3122c)：统一 CI 和 release wheel build。
- [`df508641`](https://github.com/kvcache-ai/Mooncake/commit/df508641d76be20803349bf715d3bfc5205a7b58)：增加 ROCm/HIP wheel、CI 和 release；[`14d39fff`](https://github.com/kvcache-ai/Mooncake/commit/14d39ffff518d6df7af2281ad55b2e908fe22c35) 增加 CUDA 13 EFA wheel。
- [`3dabe129`](https://github.com/kvcache-ai/Mooncake/commit/3dabe12911864084819d3868eb5094bcc9500bb5)：用 `CUDAToolkit` discovery 替代硬编码 CUDA path；[`19695872`](https://github.com/kvcache-ai/Mooncake/commit/1969587282ee4d71c61d1ced97e25b7755f182fd) 修复 no-driver build 的 CUDA stubs link path。
- [`6be6fd64`](https://github.com/kvcache-ai/Mooncake/commit/6be6fd64d157ccbd6ffd3beb8e0171fe8b27f4c9)：PG 与 PyTorch 解耦；`build_wheel.sh` 现在可打包 host-only `libmooncake_pg.so`。

新 tip 的 `scripts/build_wheel.sh` 仍明确包含 `NPU_BUILD`，并保留 NPU strip、RPATH、auditwheel 和 repack 路径，见 [`build_wheel.sh:158-190`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/scripts/build_wheel.sh#L158-L190)、[`build_wheel.sh:223-230`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/scripts/build_wheel.sh#L223-L230) 和 [`build_wheel.sh:513-535`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/scripts/build_wheel.sh#L513-L535)。因此不是“新 feature 删除 NPU wheel”，但采用 `df3f74ed` 必须重建：旧 wheel 既不含新版 feature，也不含新 base 的广泛 C++/build 变化，不能只凭相同的 `0.3.12.post1` version 判断等价。

## 对当前 vLLM-Ascend 的 compatibility 影响

### 无需修改

- `MOONCAKE_LAYERWISE_CLIENT_METHODS` 检查的七个名称与新 pybind 完全一致；adapter 的 Backend 内部接口也无需改变。[`mooncake_backend.py:31-39`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py#L31-L39)
- `batch_put_start` 仍以 `(keys, sizes)` 调 Python client，使用默认 `ReplicateConfig`。新版默认仍为 `replica_num=1,nof_replica_num=0`，不会触发 reliable NoF rejection。[`mooncake_backend.py:223-271`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/backend/mooncake_backend.py#L223-L271) [`replica.h:81-99`](https://github.com/ascend-direct-dev/Mooncake/blob/df3f74ed8ebdb0c935554beea6299a9f11c723e2/mooncake-store/include/replica.h#L81-L99)
- `test_backend.py` 已检查七个 delegation 的参数和返回类型；API surface 角度无需改 expected method names。[`test_backend.py:494-520`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/tests/ut/distributed/ascend_store/test_backend.py#L494-L520)
- final-layer commit 已按逐 key结果只 revoke 失败 keys；新版“end 失败保留 session”使这一正常 cleanup 路径更可靠。[`kv_transfer.py:1667-1696`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py#L1667-L1696)

### 可能需要修改或至少验证

最高优先级是 revoke retry ownership。新 Mooncake revoke 失败会保留 sealed `put_sessions_[key]`，以便 caller retry；当前 `_revoke_range_keys` 对 nonzero、exception 或 shape error 只 log，`finally` 中无条件删除 `_put_started_keys` 和 session tracker，并明确依赖 Master TTL。[`kv_transfer.py:1614-1633`](https://github.com/jiahaoliang/vllm-ascend/blob/6bf3fb04c2fe1b52c7a369aa13c5e1e9fd43f4c7/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/kv_transfer.py#L1614-L1633)

Master TTL 不会清除同进程 Mooncake 的 sealed local map。若 revoke 暂态失败，vLLM-Ascend 已忘记该 key，但下次 start 会被 Mooncake 以 existing session 拒绝。采用前应在以下方案中明确一个，并添加 failure-injection UT：

- vLLM-Ascend 在 revoke 失败时保留 pending cleanup ownership，并有界重试；成功或 `OBJECT_NOT_FOUND` 后再清 tracker；或
- 扩展 backend/Mooncake 提供明确的 local-session abort/cleanup 契约；或
- 若仍选择只依赖进程重启，必须把它记录为已接受的降级，而不能继续用 Master TTL 解释 local cleanup。

其次必须用新 wheel 验证：

1. 在 CPU 环境加载实际 `mooncake.store`，执行 method-presence、pybind 参数、per-key result shape 和新增 failure semantics tests；MagicMock delegation 不足以验证 ABI。
2. 编译 pinned `df3f74ed` 的 ARM64 NPU wheel，并记录 source SHA、wheel version/digest；相同 version string 不是 provenance。
3. 在 Ascend 路径执行多 key、多 fragment ranged put/get，检查 correctness、ADXL batch/submission 数和性能，覆盖 normal 与 RoCE dummy-real dispatcher。
4. 注入 concurrent end/revoke、Master RPC shape/per-key failure、flexible dual NoF 和 same-key retry。
5. 分别验证 current direct RealClient FabricMem 与 standalone dummy-real FabricMem，确认 `ShmHelper` 是否进入预期 VMM/memfd 分支且 allocate/free 配对。

## 采用建议

不要仅因为 public API 未变就直接更新 lock。推荐顺序是：先处理/定案 revoke retry ownership 和 FabricMem `ShmHelper` 差异；再构建 pinned `df3f74ed` wheel并执行 Mooncake C++/pybind focused tests；随后运行当前 vLLM-Ascend focused AscendStore UT；最后用真实 Ascend 做 scatter correctness、并发 failure injection 和 layerwise smoke/stress。以上通过后，才将 Mooncake lock 从 `786c77ff` 更新到 `df3f74ed`。

本报告只完成源码和 Git history 核对，没有声称上述运行时验证已经通过。
