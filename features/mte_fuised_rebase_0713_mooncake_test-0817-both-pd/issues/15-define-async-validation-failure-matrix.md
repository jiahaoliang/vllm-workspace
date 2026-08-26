# 定义 async validation、failure 与 compatibility matrix

Type: grilling
Status: resolved
Blocked by: 08, 09, 12, 13, 14, 17
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

哪些 static、metadata、real Scheduler async queue、worker、preemption、terminal、failure 与 default V1 tests 足以作为 implementation completion gate？Matrix 如何覆盖 sync/async 共用路径、queue depth > 1、`P TP8 -> D TP8` 与 `P TP8 -> D TP2`、normal finish/abort、late old-epoch progress、D2H fail-fast与default V1 isolation，同时只把default `MultiprocExecutor` + default `AsyncScheduler`纳入async validation target，把其他executor/scheduler组合保留为允许启动、startup warning且“未测试”，并明确Blockwise DSA与speculative config的组合虽不拒绝启动、但不做validation且不进入correctness/support claim，最后把NPU/graph-capture/runtime证据保持为`planned / not run`？

## Answer

Decision asset: [ADR 0030 - 初版 async 只验证 GitCode reporter happy path](../docs/adr/0030-validate-only-the-gitcode-reporter-async-happy-path.md)。

### Completion claim

初版 async implementation completion gate只验证[GitCode issue 1 snapshot](../references/snapshots/gitcode-vllm-ascend-issue-1-2026-08-26.md)中的单请求happy path。全部mandatory row通过后，只能对相同source identity声明`GitCode reporter happy path已通过CPU/mock validation`；不使用宽泛的`async CPU/mock validated`，也不把CPU/mock结果提升为真实reporter deployment、NPU、Mooncake transfer、fused kernel或graph-capture runtime已经通过。

Reporter配置按`P DP2/TP8 -> D DP2/TP8`、default `MultiprocExecutor`与default `AsyncScheduler`建模。Snapshot没有显式executor override，因此default `MultiprocExecutor`是基于当前vLLM默认选择的推断；隐藏template或环境变量override不在本gate内。任一mandatory row失败或未运行时，整体状态保持`not validated`。

### Minimal mandatory gate

| Layer | Mandatory case | Oracle |
| --- | --- | --- |
| Static | 修改文件compile/import、focused test collection、`git diff --check`、ruff check/format baseline delta；新增文件必须clean | 没有新增static failure，focused target可以collection |
| Startup | Decode `dsa_pd_offload=true`、default `MultiprocExecutor`、default `AsyncScheduler` | 不再触发broad async startup rejection，且不产生unverified warning |
| Async happy path | 单请求先完成`RECEIVE_REMOTE`，再由真实`AsyncScheduler`与EngineCore batch queue连续发布两个Decode step，使queue depth达到2；production DSA scheduler/worker connector使用fake model executor、Mooncake、SFA、NPU tensor与executor worker process | 两个step-local D2H plan连续；worker按FIFO处理，并只在fake `wait_for_save()`成功后返回exact TP8 progress；scheduler连续推进confirmed watermark；normal finish经`QUIESCE`与ordinary all-worker completion后release-once |
| Reporter topology | 上述trace分别使用Decode DP rank 0与1，每个replica独立聚合TP rank `0..7` | 两个DP replica不混合progress、ledger、binding或reservation |
| Narrow regression | 同一单请求happy path的sync简化trace；`dsa_pd_offload=false` default V1 isolation smoke；非默认executor/scheduler startup classification参数化smoke | Sync共用路径完成；default V1不构造DSA metadata/reservation/warning；非默认组合允许启动并只warning一次，列出实际executor/scheduler和“未测试” |

Real `AsyncScheduler`与EngineCore queue orchestration属于被执行组件；实际model execution、Mooncake、SFA kernel、NPU tensor和`MultiprocExecutor` worker process均由CPU fake/mock替代。初版不要求broad CPU/mock root、完整Phase B rerun或真实multiprocess/NPU execution。

### Compatibility and deferred matrix

| Combination or case | Initial evidence status |
| --- | --- |
| Default `MultiprocExecutor` + default `AsyncScheduler` + reporter logical topology happy path | Mandatory CPU/mock gate；通过前为`not validated` |
| Default combination上的preemption、abort、D2H failure、late progress、adversarial metadata、多请求交错与`P TP8 -> D TP2` | 未测试 |
| Ray、`UniProcExecutor`、external launcher、`BalanceScheduler`、custom executor/scheduler及其lifecycle | 未测试 |
| Blockwise DSA与speculative config | 未测试 |
| NPU、真实Mooncake transfer、fused kernel与graph-capture runtime | `planned / not run` |

Deferred rows不进入初版completion gate。它们已接受的preemption、terminal、failure、ledger与ownership设计合同保持不变，但本gate不提供这些合同已经通过测试的证据。非默认executor/scheduler仍按[定义 async executor compatibility boundary](17-define-async-executor-compatibility-boundary.md)允许启动并warning为“未测试”；warning和compatibility文档不说明影响范围。

本ticket只定义后续implementation gate，没有修改production source或运行source tests。具体spec/ADR supersession与implementation/test ticket chain由[定义 ADR/spec supersession 与 implementation ticket chain](16-define-doc-supersession-implementation-chain.md)继续决定。
