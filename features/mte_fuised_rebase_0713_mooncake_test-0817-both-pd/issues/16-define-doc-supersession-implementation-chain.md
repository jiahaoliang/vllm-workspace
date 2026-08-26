# 定义 ADR/spec supersession 与 implementation ticket chain

Type: grilling
Status: resolved
Blocked by: 10, 11, 12, 13, 14, 15
Parent: [Blockwise DSA Async Scheduling Wayfinder Map](../map.md)

## Question

最终 async-compatible contract 应如何更新 `CONTEXT.md` 与 spec，哪些 ADR/approved amendments 需要部分 supersede、仅补充引用或保持不变？文档如何同时保留完整lifecycle correctness设计、又把初版completion claim严格收窄为GitCode reporter `P DP2/TP8 -> D DP2/TP8`单请求happy path的CPU/mock validation，并将完整failure/lifecycle matrix标记“未测试”、NPU/graph-capture标记`planned / not run`？在不修改production source的本map destination内，后续implementation/test work应按哪些最小vertical slices与blocking顺序拆成可独立验收的ticket chain？

## Answer

### Canonical contract and evidence

[spec.md](../spec.md)原位升级为唯一async-compatible交付合同，并明确区分三个事实层：

- 已发布sync replacement `7401ae79c`及其既有CPU/mock evidence继续有效；
- async delta已批准但production implementation尚未开始；
- GitCode reporter async happy path、完整failure/lifecycle matrix和真实runtime evidence分别按实际状态报告。

完整terminal、preemption、late-progress等lifecycle design属于production implementation scope，但初版completion gate只验证GitCode reporter的`P DP2/TP8 -> D DP2/TP8`、default `MultiprocExecutor` + default `AsyncScheduler`单请求happy path。Preemption、abort、D2H failure、late progress、adversarial metadata、多请求交错、asymmetric TP、speculative与非默认executor/scheduler lifecycle只写“未测试”；NPU、真实Mooncake、fused kernel与graph-capture保持`planned / not run`。Gate通过后唯一允许的新claim是：

`GitCode reporter happy path 已通过 CPU/mock validation`

不能写成广义`async CPU/mock validated`或真实reporter deployment/runtime已通过。

[CONTEXT.md](../CONTEXT.md)保留Phase A/Phase B术语，但把它们限定为已发布sync replacement的历史validation stages；async初版gate使用现有`GitCode reporter happy-path CPU/mock validation`术语。

### Supersession

旧ADR正文保留当时的decision history，只在状态行和短后续关系中记录lineage：

- ADR 0009的async validity cut/barrier部分由ADR 0024、0026取代；
- ADR 0017-0021中的decode-time `FUSED_D2H`、`D2H_COMPLETE`、D2H fields和cross-step typed-result gate由ADR 0024、0027取代；
- ADR 0010由ADR 0025扩展到所有terminal reason；
- ADR 0023的async初版completion gate由ADR 0030取代，sync Phase A/Phase B evidence保留；
- ADR 0012、0013、0016继续有效，并分别约束transfer-failure replay与unquiesced barrier；
- ADR 0001-0008、0011-0016中未列出的稳定合同以及ADR 0022保持不变；ADR 0024-0030是当前async delta。

[blockwise-dsa-pd-offload-design.md](../blockwise-dsa-pd-offload-design.md)、旧reimplementation goal和冲突的Stage 1/Stage 3/white-box amendments标记为sync replacement历史baseline并指向当前spec/ADR，不改写其历史正文或测试数字。Routing、reservation queue与stale-result等无冲突amendments保持不变。README/status增加async delta状态；validation report、repo-state、runbook、snapshot与transcript作为历史evidence不修改。

旧replacement的`1770/1500`行数stop lines和source/test授权不延伸到async delta。新tickets采用范围型stop-and-review；创建ticket本身不授权修改`repos/*`。

### Implementation/test ticket chain

- [18 — 实现 non-gating D2H plan/progress vertical slice](18-implement-non-gating-d2h-plan-progress.md)：metadata、issued/confirmed ledger、persistent worker Main binding、per-step SFA view与`wait_for_save()` progress的两步闭环。
- [19 — 实现 async terminal ownership barrier](19-implement-async-terminal-ownership-barrier.md)：blocked by 18；实现unified `Terminal-pending`、FIFO `QUIESCE`、ordinary all-worker completion与release-once，初版只测normal finish。
- [20 — 实现 async preemption replay barrier](20-implement-async-preemption-replay-barrier.md)：blocked by 18；实现epoch cut、new-epoch rebind与exact-TP `REPLAY_READY`，初版只做static/import，Preemption写“未测试”。
- [21 — 实现 async compatibility warning与unverified startup policy](21-implement-async-compatibility-warning-policy.md)：可并行；只测default no-warning与一个非默认warning，speculative允许启动但不测试。
- [22 — 验证 GitCode reporter async happy path](22-validate-gitcode-reporter-async-happy-path.md)：blocked by 18-21；使用真实`AsyncScheduler`与EngineCore depth-2 queue、production DSA connector和fake/mock external execution boundaries完成最终最小gate。

这些implementation tickets保持`open`，不是新的Wayfinder decision frontier。后续session必须单独认领、核对source baseline/dirty state并取得production source修改授权。本ticket只完成control-repo文档与执行路线规划；未修改`repos/*`、未运行source tests或NPU workload。
