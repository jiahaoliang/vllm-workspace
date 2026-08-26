# 定义 async executor compatibility boundary

Type: grilling
Status: resolved
Blocked by: 08
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

首版 Blockwise DSA async scheduling 应对哪些 executor / scheduler 组合给出 correctness guarantee？是否只承诺 source-audited default `MultiprocExecutor`，对 Ray、external launcher、BalanceScheduler 或其他未验证组合 startup fail closed；还是要求把其中哪些组合纳入同一 contract 与 CPU/mock completion gate？该边界如何表述，才能不把 topology 支持误写成 executor 支持，也不把未运行的 NPU/graph-capture 证据描述为已验证？

## Answer

Decision asset: [ADR 0029 - 只验证 default MultiprocExecutor 与 default AsyncScheduler](../docs/adr/0029-validate-only-default-multiproc-and-async-scheduler.md)。

### First-version validation target

首版唯一的 async executor compatibility validation target 是 default `MultiprocExecutor` 与 default `AsyncScheduler` 的组合。这里的 default 组合包括显式或自动选择 `distributed_executor_backend="mp"`、且没有 custom scheduler 或 Ascend `BalanceScheduler` override 的标准 async scheduling path；`RayExecutorV2` 即使继承 `MultiprocExecutor` 也不自动属于该组合。

该边界只决定 async validation 与 correctness claim，不收窄现有 sync path，也不改变 Prefill、`dsa_pd_offload=false` 的 default `MooncakeConnectorV1` 或已经单独决定的 speculative config 边界。Executor classification 与 topology 分开：`P_TP >= D_TP`、`P_TP % D_TP == 0`、DP2/TP8 或其他合法 P/D topology 都不能单独证明 executor compatibility。GitCode reporter 的 DP2/TP8 环境在未被 template 或环境变量覆盖 backend/scheduler 时落入 default combination。

### Startup 与 unverified classification

Ray、`UniProcExecutor`、external launcher、`BalanceScheduler`、custom executor/scheduler 与其他非默认组合都不做 Blockwise DSA-specific startup fail closed。Decode 在 `dsa_pd_offload=true` 与 async scheduling 同时启用、且实际 executor/scheduler 不属于 default combination 时仍允许启动，但输出一次 warning，列出实际 executor/scheduler 并标记 `unverified` / “未测试”。Warning、compatibility matrix 与用户文档不展开未测试组合可能影响的具体 contract 范围。

这一选择不把未测试组合提升为 validation target，也不把“允许启动”写成已验证。相反，只有 default `MultiprocExecutor` + default `AsyncScheduler` 进入本 map 后续的 static 与 CPU/mock completion gate。

### Promotion 与 evidence language

Upstream `supports_async_scheduling()`、class inheritance 或一次无报错运行都不能自动把组合升级为 validated。新增组合必须先完成对应 executor/scheduler 的 source audit，证明 per-worker step FIFO、FIFO output consumption、all-worker aggregation 与 metadata-only/no-forward batch ordering，再通过与 default combination 相同的 CPU/mock completion gate，并显式更新 compatibility matrix。

Spec 可以为 default combination 定义 correctness contract；实现和报告只有在后续 matrix 的 static 与 CPU/mock gate 实际通过后才能写 `CPU/mock validated`。Ray、`UniProcExecutor`、external launcher、`BalanceScheduler`、custom combination、NPU runtime 与 graph-capture runtime 在没有各自证据时只写 `unverified` 或 `planned / not run`，不能从 topology、source contract 或其他测试层推断。

Current replacement `7401ae79c`仍在 Decode `dsa_pd_offload=true`与async scheduling同时启用时统一拒绝启动。目标实现需要删除这条 broad rejection，并以 default-combination validation target、非默认组合warning和文档分类取代；本ticket未修改production source或运行source tests。
