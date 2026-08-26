# Blockwise DSA PD Offload 重实现 Stage 1 Design Gate

状态：已批准并用于sync replacement；metadata D2H与validation条款已被ADR 0024、0027、0030部分取代；其余baseline contract保留

## 1. 本门禁的依据

- Durable goal：`reimplementation-goal.md`
- 干净重实现基线：vLLM-Ascend `0d6dd0d26ab69219f861c9b312329f4c60fe36f2`
- Behavior/test oracle：`60eb76e46225e9aaec1493fb247313f8642486ad`
- 当前 accepted contract：`spec.md`、ADR 0002、ADR 0017-0022
- 设计原则：一个主 `MooncakeConnectorV1` lifecycle seam、一个 typed metadata support seam、一个 SFA memory/data-plane support seam

`60eb76e` 只提供行为线索和 CPU/mock oracle，不是 replacement base，也不是可发布实现。当前 NPU 状态仍为 `planned / not run`。

## 2. 结论

Replacement 不保留 standalone DSA subsystem。目标 implementation 只有以下 module shape：

1. `MooncakeConnector` 继续是唯一公开 connector interface。
2. `mooncake_connector.py` 内增加 opt-in wiring，以及一个 private、继承 `SFAPDCpuOffloadScheduler` 的 Decode scheduler implementation。
3. 新增一个 feature-local `mooncake_dsa_metadata.py`，只定义 cross-process typed command/result contract 和 same-step result merge。
4. 直接扩展现有 `MooncakeConnectorWorker`、`KVCacheRecvingThread` 与 `KVCacheSendingThread`，复用已有 endpoint、handshake、socket、Mooncake engine、request queue、delayed-free 和 `DONE_RECVING_MSG` flow。
5. Decode worker 直接组合现有 `SFAKVOffloadWorker`，复用 per-TP Host Main pool、runner binding、CPU block table、fused D2H、TP failure propagation 和 save drain。
6. 仅当既有接口无法表达真实 capacity 或 bound range 时，给现有 SFA scheduler/worker 增加 protected helper；不建立新的 scheduler、runtime、executor、worker wrapper、transport、rendezvous 或 memory subsystem。

这满足 ADR 0002 对 `SFAPDCpuOffloadScheduler` 继承路径的明确要求。基线已有 `MooncakeToDramDecodeScheduler(SFAPDCpuOffloadScheduler)` 先例，证明 subclass seam 可行。

## 3. `60eb76e` 规模与偏离

`0d6dd0d -> 60eb76e` 的实际 diff：

| 类别 | 文件数 | Additions | Deletions |
|---|---:|---:|---:|
| Production | 14 | 6,283 | 9 |
| Tests | 15 | 6,034 | 0 |
| 合计 | 29 | 12,317 | 9 |

主要膨胀来自 13 个新 production modules：

- `mooncake_dsa_scheduler.py`：1,259 行
- `mooncake_dsa_worker.py`：616 行
- `mooncake_dsa_transport.py`：554 行
- `mooncake_dsa_prefill_worker_adapter.py`：528 行
- `mooncake_dsa_memory.py`：523 行
- `mooncake_dsa_decode_worker.py`：462 行
- `mooncake_dsa_decode_runtime.py`：451 行
- `mooncake_dsa_metadata.py`：391 行
- `mooncake_dsa_data_plane.py`：338 行
- `mooncake_dsa_lifecycle.py`：329 行
- `mooncake_dsa_config.py`：296 行
- `mooncake_dsa_rendezvous.py`：192 行
- `mooncake_dsa_worker_adapter.py`：62 行

`MooncakeDsaScheduler` 没有继承 `SFAPDCpuOffloadScheduler`，直接违反 ADR 0002。`MainReservationManager`、`DsaLifecycleAccumulator` 和 `MooncakeDsaScheduler` 均只有一个 production caller；runtime、executor、memory adapter 和 worker wrappers 也镜像了现有 worker/SFA/Mooncake state。按 deletion test，删除它们不会把复杂度扩散到多个 caller，而是让职责回到已有深 module，因此它们不应迁移。

## 4. Replacement 必须保留的 externally observable behavior

### 4.1 Opt-in 与 default isolation

- `dsa_pd_offload` 只能由显式 boolean `true` 开启。
- 缺失或 `false` 时，不解析 DSA-only config，不构造 DSA/SFA state，普通 `MooncakeConnectorScheduler`、`MooncakeConnectorWorker`、metadata、transfer、completion 与调用协议保持不变。
- Prefill 只允许 `kv_producer`、不启用 offload；Decode 只允许 `kv_consumer`、启用 `fused_overlap` 和 Mooncake SFA backend。
- Fail closed：`P_TP < D_TP`、`P_TP % D_TP != 0`、Decode PP != 1、Decode `DCP * PCP != 1`、role/mode/type mismatch。
- Prefill scheduler 始终是普通 `MooncakeConnectorScheduler`；Prefill 不分配 Decode Host blocks，不运行 SFA scheduler，不使用 layerwise save/load flow。
- Decode 继续通过 `MooncakeConnector` 的 public hooks 完成 metadata bind、worker result、scheduler output、Host Main binding、fused D2H、LRU/load 和 request IDs。

### 4.2 Positional data plane

- 保留普通 V1 Decode-initiated、request-level、blockwise pull；不迁移 Prefill layerwise push。
- Handshake 只携带 layer-keyed positional arrays：`tensor_group_idx[]`、`kv_caches_base_addr[]`、`block_len[]`、`block_size_scale[]` 和现有 endpoint/TE port。
- 不增加 semantic role、protocol version、compatibility hash、dtype/shape/memory-kind proof 或 connector-side cross-deployment validation。
- Prefill 注册并发布 Main K/V、Indexer 和可选 Indexer scale；复用已有 `GET_META_MSG`、socket、delayed-free 和 `DONE_RECVING_MSG` flow。
- 固定 leader：`source_rank = decode_tp_rank * (P_TP / D_TP)`；不使用普通 V1 的 request-hash/random replica selection。
- 每个 Decode TP 只注册自己的 Indexer HBM 与 runner-owned、NPU-addressable Swapped Main pool；block ID 0 保留。
- Scheduler capacity 来自同一个 `kv_cache_config`；每个 worker 在 local registration 时校验 runner tensor capacity 和 registered range 与该 capacity 一致。任一 rank 本地不一致即 startup fail closed。
- Main K/V block geometry相同；Indexer page ratio只能为正整数；partial request仍按完整物理 block/page transfer，token有效范围继续由 vLLM request token state提供。

### 4.3 Admission、receive 与 failure

- Decode admission 前按 `prompt + max output` 建立 Main lifetime reservation。
- Capacity不足时保持 waiting，不回退 local Prefill；一个 scheduling step内首个 miss 后启用 HOL gate，下一 step重新判断。
- 一个 worker 的 `RECEIVE_REMOTE` 内先进行一次同步 Indexer D2D；只有成功后才进行一次同步 Main D2RH。
- Python connector不增加 outer retry；仅依赖 Mooncake binding internal retry。
- 成功产生 `RECEIVE_COMPLETE`；失败产生 `TRANSFER_FAILED(INDEXER_D2D)` 或 `TRANSFER_FAILED(MAIN_D2RH)`。
- 只有 exact Decode TP rank coverage 全为 `RECEIVE_COMPLETE`，scheduler才向 core 暴露 receive completion。
- 任一 TP failure 后仍等待当前 command 的全部 TP terminal results，不能与其他 TP 尚未完成的 DMA 并发进入 replay。
- Programming error、非法 layout、非法 ownership 或不可能状态继续 fail fast；只把明确的同步 transfer final failure转换成 recoverable typed `TRANSFER_FAILED`。

### 4.4 Typed metadata 与 exact TP

- 独立 nested command contract：顶层 request identity，加 `RemoteSource`、`DestinationOwnership`、`LifecycleCommand`。
- Actions固定为 `RECEIVE_REMOTE`、`FUSED_D2H`、`PREPARE_REPLAY`、`QUIESCE`。
- Typed terminal results固定为 `RECEIVE_COMPLETE`、`D2H_COMPLETE`、`REPLAY_READY`、带 phase 的 `TRANSFER_FAILED`；`QUIESCE` 不产生 typed result。
- Result identity固定为 `(request_id, execution_epoch, command_seq, tp_rank)`。
- `KVConnectorWorkerMetadata.aggregate()` 只合并 same-step facts；scheduler按 command identity跨 step累计。
- 相同完整 result duplicate幂等；conflict、future、illegal rank、action/result mismatch fail closed；stale记录并忽略；missing rank持续 pending。
- Typed metadata是 immutable snapshot，不拥有 lifecycle state，不携带 tensor、thread、event 或 process-local raw object。

### 4.5 Fused D2H、replay 与 preemption

- `FUSED_D2H` 从 confirmed Main boundary开始，只访问当前 command bound Host prefix。
- 复用 `SFAKVOffloadWorker.save_current_kv_tokens()` 和 save drain；只有成功后产生 `D2H_COMPLETE`。
- Exact TP `D2H_COMPLETE` 推进 confirmed Main prefix，但不产生 ordinary receive completion。
- Fused D2H failure保持 worker/engine fail-fast，不伪造 typed result或 `finished_recving`。
- Transfer failure保留 reservation identity，但令所有 TP `preserved_main_tokens=0`；exact terminal coverage后下发 `PREPARE_REPLAY`。
- Exact TP `REPLAY_READY` 后，scheduler先把 request token state置为从 token 0 full-sequence replay，再产生允许 core推进的 completion。
- Preemption保留 Main reservation，retire旧 epoch，并用 core新分配的 Indexer IDs建立新 epoch。Main ownership/layout/validity连续时保留 confirmed prefix，否则降为0。
- Replay token数、复用 Main token数和 skipped D2H bytes只作为 scheduler transition的结构化日志/观测，不建立 snapshot subsystem。

### 4.6 Cancellation 与 cleanup

- Admission 前 cancellation可立即结束；admission后进入 cancel-pending、阻止新 receive/replay/D2H并保留 ownership。
- Worker drain当前 Mooncake/SFA operation；无法证明 Quiesced时保持 pending/隔离，不增加 watchdog、可靠 native cancel或 timeout强制释放。
- Quiesced 后，worker先对实际使用且尚未通知的 Prefill source best-effort发送一次现有 `DONE_RECVING_MSG`，再一次性放入 ordinary `finished_recving`。
- Cancellation 不产生 typed `QUIESCED`；由现有 `KVOutputAggregator` 做 ordinary all-worker completion。
- Scheduler只在 all-worker completion后 release-once Main reservation；重复/late ack不 double free，core随后按现有顺序释放 delayed NPU blocks。
- 普通 receive已通知的 source不因 cancellation重发。
- Proposed implementation detail：明确的 transfer terminal failure后也可复用现有 best-effort source release，因为 Decode不会再次读取该 source；该通知不代表 Decode receive成功，也不能产生 `finished_recving`。若编码发现现有 normal receiver已经无条件发送，可保留其 source-lifetime语义，但必须隔离 Decode lifecycle结果。

### 4.7 Evidence boundary

- Phase A/B CPU/mock只证明 Python contract、ordering、state transition和fake transfer边界。
- CPU/mock不能证明真实 NPU-addressable Host registration、D2D、D2RH、fused kernel、cache内容正确性或性能。
- NPU未真实执行前始终为 `planned / not run`。

## 5. 不迁移的 `60eb76e` 行为

- `MooncakeDsaScheduler`、`MainReservationManager`、`DsaLifecycleAccumulator`、`DsaWorkerLifecycleExecutor`、`DsaWorkerAdapter`、`MooncakeDsaDecodeRuntime`、`MooncakeDsaDecodeWorker` 和 Prefill adapter 的 class/interface形状。
- 独立 transport、rendezvous、memory、data-plane、config 和 lifecycle modules。
- Lazy decode-worker factory、callback必须返回 bool、内部 snapshot字段、history列表和 exact exception文案。
- `DsaPrefillTupleLayout.PACKED_MAIN_INDEXER_SCALE`；public connector已经拒绝它，属于 unreachable test artifact。
- 将任意 Python exception吞成 recoverable transfer failure。
- 把 `use_layerwise=true` 暴露为 DSA产品 contract。Decode内部可按现有 `SFAKVOffloadWorker`要求使用其 layer-oriented implementation，但不改变 Prefill no-layerwise contract。
- 把 `command_seq + 1`、`epoch + 1` 或每个 epoch从0开始固定为 wire contract；只保留 strictly increasing和 stale/future规则。
- 把 GET_META无 retry测试扩大成 ADR 0014 的 transfer-phase no-outer-retry contract。
- 为每个被删除的 shallow module迁移镜像 unit tests。

## 6. Existing code reuse matrix

| Existing module/interface | 直接复用 | Thin extension |
|---|---|---|
| `MooncakeConnector` | 唯一 public connector与现有 hooks | opt-in type gating、`build_connector_worker_meta()`、`update_connector_output()` 和 SFA hook forwarding |
| `MooncakeConnectorScheduler` | Prefill全部行为；普通 Decode default path | DSA Decode不修改它 |
| `SFAPDCpuOffloadScheduler` | SFA config、group geometry、Decode pull判定、`SchedulerOutput` traversal、CPU allocator基础 | private subclass覆盖 lifetime reservation、HOL、epoch、typed command、exact TP transition、preemption/cancellation/release |
| `CPUBlockManager` | block 0保留、free-list分配与回收 | 参数化真实 fused Host capacity；不新增 reservation manager |
| `MooncakeConnectorWorker` | topology、TP rank、ports、engine、sender/receiver和public worker hooks | DSA positional registration、fixed leader、command guard、typed result queue、quiesce/once state，直接组合 SFA worker |
| `KVCacheSendingThread` | GET_META、arbitrary msgpack response、delayed-free、DONE/ACK | 发送 DSA positional metadata；不增加 Prefill listener |
| `KVCacheRecvingThread` | request queue、per-peer concurrency、metadata cache、socket pool、一次同步 Mooncake transfer、source notification | DSA task branch构造 Indexer/Main SG list并发出 phase-aware local result；失败不得走普通 receive completion |
| `SFAKVOffloadWorker` | runner Host binding、per-TP Host pool、Indexer discovery、CPU block table、fused D2H、TP error reduction、save drain | 从 typed DSA command投影当前 bound prefix和D2H range；必要时增加小型显式 binding helper |
| `KVConnectorWorkerMetadata`/`KVOutputAggregator` | same-step worker fact聚合接口；ordinary cancellation count | typed metadata实现same-step merge；aggregator不承担receive/replay/D2H exact rank contract |
| Mooncake TransferEngine | transfer submission、internal retry和operation return code | 无新 adapter；Python每 phase只调用一次 |

`SFAPDCpuOffloadConsumerWorker` 仅作为 delegation/cleanup参考，不直接实例化：它强制 MemFabric并按 TP0 shared owner建模，不符合每个 Decode TP独立 Swapped Main ownership。

## 7. State ownership map

| Authoritative owner | 唯一拥有的事实 | 明确不拥有 |
|---|---|---|
| vLLM `Request` / `SchedulerOutput` | request status、token progress、当前 NPU block allocation | Main Host reservation、worker operation |
| private SFA scheduler subclass in `mooncake_connector.py` | 完整 Main reservation IDs/capacity、valid prefix、epoch/sequence/action、当前 Indexer IDs、cross-step TP results、terminal intent、release-once | Host tensor、raw address、in-flight transfer |
| inherited `CPUBlockManager` | free Main block IDs | request lifecycle和validity |
| typed metadata | immutable current-command/result snapshot | mutable lifecycle、history、tensor和operation |
| `MooncakeConnectorWorker` | process-local active command guard、local result queue、cancel/Quiesced、source-notified-once、ordinary-completion-once | cross-TP completeness、future reservation list |
| `KVCacheRecvingThread` | 当前 local Mooncake operation、phase、最终 transport return | request replay/preemption/cancellation policy |
| `SFAKVOffloadWorker` | Host Main tensors、Indexer tensor binding、CPU block table、fused D2H execution和save drain | scheduler reservation和cross-TP result |
| Mooncake TransferEngine | native/internal retry和transport operation | Decode lifecycle transition |
| Prefill `KVCacheSendingThread` | Prefill source delayed-free和GET_META/DONE listener state | Decode destination ownership |
| `KVOutputAggregator` | cancellation ordinary all-worker request-ID completion | typed rank/epoch/action correctness |

每个 lifecycle fact只有一个 owner。不会再出现 runtime `_receive_executions`、executor request state、memory `_main_prefixes` 和 SFA block table同时镜像同一 Main validity的情况。

## 8. 逐文件 implementation plan 与预算

以下 additions/deletions均相对干净 base `0d6dd0d`，是批准前预算，不是 quota目标。

### Production

| File | Additions | Deletions | 计划 |
|---|---:|---:|---|
| `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py` | 700-950 | 5-25 | opt-in config；private SFA scheduler subclass；single request tracker；public lifecycle；positional Prefill/Decode registration；fixed leader；receiver DSA branch；worker command/result/quiesce；SFA delegation |
| `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_dsa_metadata.py` | 250-340 | 0 | enums、nested immutable command、typed result、central validation、same-step aggregate；不含 lifecycle manager或process-local state |
| `vllm_ascend/distributed/kv_transfer/sfa_pd_cpu_offload/scheduler.py` | 15-35 | 5-15 | parameterize真实 Host capacity或增加最小 protected allocator hook；保持默认 SFA behavior |
| `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py` | 20-60 | 0-10 | 仅在需要时增加typed bound-prefix/D2H-range helper和registration facts；复用现有execution |
| **Production total** | **985-1,385** | **10-50** | 低于 1,950 stop-and-review threshold |

明确不创建：

- `mooncake_dsa_scheduler.py`
- `mooncake_dsa_lifecycle.py`
- `mooncake_dsa_worker.py`
- `mooncake_dsa_worker_adapter.py`
- `mooncake_dsa_decode_runtime.py`
- `mooncake_dsa_decode_worker.py`
- `mooncake_dsa_transport.py`
- `mooncake_dsa_rendezvous.py`
- `mooncake_dsa_memory.py`
- `mooncake_dsa_data_plane.py`
- `mooncake_dsa_prefill_worker_adapter.py`
- standalone `mooncake_dsa_config.py`

相对 `60eb76e`，这意味着不迁移其 13 个 standalone production modules，并将 production additions从 6,283 预计收敛到 985-1,385，减少约 78%-84%。

### Tests

| File | Additions | Deletions | 计划 |
|---|---:|---:|---|
| `tests/ut/kv_offload/test_mooncake_connector.py` | 500-650 | 0-30 | public `MooncakeConnector` lifecycle：mode/default、admission、allocation、metadata、worker receive/result、scheduler consumption、replay/preemption/cancellation/release |
| `tests/ut/kv_offload/test_mooncake_dsa_metadata.py` | 180-250 | 0 | typed schema、validator、serialization-safe values、action/result matrix、same-step duplicate/conflict aggregate |
| Existing focused SFA scheduler/worker tests | 80-140 | 0-20 | capacity、runner Host binding、bound prefix、D2H range/save drain；只测主 seam不可观察的SFA事实 |
| **Focused test total** | **760-1,040** | **0-50** | 位于 spec的 700-1,100范围内，低于 1,100 stop threshold |

Tests在 main lifecycle seam存在后替换浅 module tests，不叠加迁移 `60eb` 的14个 `test_mooncake_dsa_*` suites。任何需要突破1,100行的新增测试计划都先暂停评审。

## 9. Test seam 与验证顺序

### Main seam：public `MooncakeConnector`

- Default V1 constructor、metadata type、worker calls、completion保持不变。
- DSA startup role/topology/backend constraints。
- Prefill普通 scheduler + positional registration + existing source lifetime flow。
- Decode admission、reservation、HOL、Indexer allocation和typed command。
- Fixed leader、partial physical block、Indexer-before-Main、phase-aware failure。
- Same-step worker result -> cross-step exact TP -> scheduler/core completion。
- Transfer failure all-TP barrier -> full replay -> release-once。
- Fused D2H exact TP prefix advance，无 ordinary completion。
- Preemption epoch rebind与preserved/fallback Main boundary。
- Cancellation drain、DONE-before-finished、ordinary all-worker ack、release-before-core delayed block cleanup。
- Multi-request interleaving、duplicate/conflict/stale/future/missing result。

### Support seam 1：typed metadata

- Immutable nested envelope与集中 validator。
- Action/result/failure-phase matrix。
- Same-step merge、duplicate idempotency、conflict fail closed。
- RPC/serialization-safe values。

### Support seam 2：SFA memory/data plane

- Per-TP Host tensor capacity和registration range。
- Indexer HBM/Main Host positional binding。
- Current bound prefix和preserved boundary。
- Fused D2H range、save drain和fail-fast。

Phase A先跑 mode、mapping、ordering、基本 failure/replay/default isolation。Phase B再跑 lifetime reservation、HOL、exact TP、preemption、cancellation、multi-request和negative contracts。CPU/mock必须在 `liangjiahao/vllm-ascend-ut` 中按 `AGENTS.md`同步当前 checkout并显式运行 targets；NPU remains `planned / not run`。

## 10. Oracle gaps 必须补测

`60eb76e` 现有 tests不能作为以下行为的充分证据，replacement tests必须通过 public seam补齐：

- Full-sequence replay确实从 token 0重建 Indexer并重写/保留正确 Main范围，而不只是检查 command字段。
- Preemption后的真实 replay forward和preserved Main D2H suppression。
- 普通成功、提前结束通过 public `request_finished()` release reservation。
- Reservation已建立但 Indexer binding尚未产生时的 cancellation，不能永久 delayed-free。
- Worker local capacity/registration checks与scheduler使用同一个 `kv_cache_config`事实；CPU/mock只能证明local fail-closed，不能冒充真实distributed/NPU registration。

## 11. ADR 与 threshold 对照

| Gate | 结果 |
|---|---|
| ADR 0002：Decode scheduler继承 `SFAPDCpuOffloadScheduler` | 满足；private subclass置于 `mooncake_connector.py` |
| ADR 0017-0021：独立 typed step/result metadata + exact TP | 满足；唯一新 feature module是 `mooncake_dsa_metadata.py` |
| ADR 0022：positional handshake、无 semantic negotiation | 满足；在现有 Mooncake sender/receiver内实现 |
| 一个主 lifecycle seam + 两个 support seams | 满足 |
| Production additions stop threshold 1,950 | 预算 985-1,385 |
| Focused tests stop threshold 1,100 | 预算 760-1,040 |
| Default V1 isolation | main seam必测；flag关闭时不构造DSA/SFA state |
| Standalone subsystem禁止项 | 全部不创建 |

## 12. 批准后的 Stage 2 首个动作

只有用户明确批准本 design gate 后才执行：

1. 保留当前 `60eb76e` reference checkout不动。
2. 从 `0d6dd0d26ab69219f861c9b312329f4c60fe36f2` 创建新的非破坏性 worktree/branch。
3. 先写 public connector lifecycle最小 failing tests和typed metadata tests，再按小 commit实现。
4. 每个 commit检查实际 diffstat与本预算；production additions预计超过1,950、focused tests预计超过1,100，或需要新增任何禁止的 standalone module时立即停止并回到设计评审。
5. 在任何 push、lock、repo-state、issue/status更新前再次展示base/head、完整diffstat、tests、风险和staging allowlist，并等待明确批准。
