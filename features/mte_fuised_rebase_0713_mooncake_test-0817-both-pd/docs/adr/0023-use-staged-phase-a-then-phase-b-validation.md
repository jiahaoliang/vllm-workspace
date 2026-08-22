# 使用 Phase A 后 Phase B 的分阶段验证

状态：已接受

Blockwise DSA PD offload 采用分阶段测试门禁。实现首先运行范围较小的 Phase A，快速验证 opt-in 数据面和最小 request lifecycle；Phase A 通过后必须继续扩展并运行 Phase B，覆盖已经接受的 reservation、failure、aggregation 和 cleanup 边界。Phase A 是快速迭代检查点，不是最终 CPU/mock 验收标准。

真实 NPU end-to-end 测试不在当前环境执行。本工作生成以 `P TP8/DP2 -> D TP2/DP8` 为起点的测试计划，并始终把计划与已执行证据分开。只有未来真实执行 NPU 计划并满足成功标准后，才能声称 runtime correctness 已验证。

## 穿刺代码怎么做

穿刺 connector 将 Indexer D2D 和 Main D2RH 拆成两个 `TransferSync` batch，并按 Indexer、Main 的源码顺序调用。现有 focused tests 覆盖 positional 地址计算、D2D/D2RH SG list 分离、Indexer page packing、TP port mapping，以及部分单 rank Swapped Main/Indexer destination 构造。

穿刺没有实现目标状态机的完整测试门禁。尤其是，Indexer transfer 返回失败时，当前 `_transfer_one_leg()` 只记录 `failed_reqs`，随后仍会无条件调用 Main leg；已有 helper test 证明两条 SG list 被拆开，但没有证明“Indexer 失败即不启动 Main”。穿刺测试也没有完整覆盖 request-lifetime reservation、head-of-line admission、execution epoch、两阶段 cancellation、full-sequence replay 或 exact TP result coverage。

因此目标实现可以复用穿刺 fixture 和地址 oracle，但不能把穿刺测试集原样当作 Phase A 或 Phase B 的充分验收证据。

## 普通 MooncakeConnectorV1 和 vLLM 怎么做

普通 V1 将当前请求的 `GroupPull` 生成统一的 `src_list`、`dst_list` 和 `length_list`，然后调用一次 `batch_transfer_sync_read()`；transfer 返回失败时抛出 `RuntimeError`。现有 tests 覆盖普通 block mapping、TP/CP/PP split、scheduler delegation 和成功/失败路径，但不存在 DSA Main reservation、Indexer-before-Main gate、execution epoch、lifecycle command 或 rank-aware terminal result。

两个阶段都必须保留 default V1 isolation test：`dsa_pd_offload=false` 时继续实例化并执行原有 V1 metadata、scheduler 和 worker path，不构造 DSA envelope，也不分配 Swapped Main lifetime reservation。

## Phase A：快速基本功能门禁

Phase A 只覆盖足以尽早发现集成方向错误的 deterministic static 和 CPU/mock tests：

- `dsa_pd_offload` opt-in 配置选择正确，关闭时普通 V1 路径不变；
- startup 拒绝已确定的非法 topology、Decode PP、`DCP * PCP` 和不足以服务单请求上限的 Swapped Main capacity；
- positional layer metadata 的本地数组等长、地址、block length/scale 和缺失 layer 检查；
- fixed TP leader 和 block ID 到 source/destination address 的基本映射，partial block 按完整物理 block 传输；
- 单请求成功路径严格按 Indexer D2D 后 Main D2RH 调用，两个 phase 在 Python connector 边界各调用一次；
- Indexer failure 不调用 Main，并产生 `TRANSFER_FAILED(INDEXER_D2D)`；Main failure 产生 `TRANSFER_FAILED(MAIN_D2RH)`；
- 单 rank 或最小 mocked TP coverage 下，receive success 能建立有效状态，failure 能进入 `PREPARE_REPLAY`，terminal cleanup 对 Main reservation release-once；
- 所有本次修改的 Python 文件通过项目要求的 focused static checks。

Phase A 通过的含义是“基本功能线可以继续扩展”，不表示并发、乱序、preemption、cancellation、资源压力或跨 TP failure 已验证。Phase A 失败时先修复基本路径，不继续堆叠 Phase B case。

预计 Phase A 增加约 350-600 行 focused tests，测试实现与修复约 2-4 个工程日，不包含 production implementation 和 NPU 执行时间。

## Phase B：边界与状态机门禁

Phase A 全部通过后，Phase B 在相同实现上补齐 contract-complete CPU/mock matrix：

- reservation/admission：完整 request-lifetime capacity、per-step head-of-line blocking、等待期间不泄漏 ownership、release-once 和重复 cleanup；
- preemption：旧 epoch retire、新 Indexer IDs rebind、Main reservation 跨 epoch 保留、confirmed Main prefix 不重复 D2H；
- cancellation：各 lifecycle 阶段下发 `QUIESCE`、operation drain 前保持隔离、每个 worker 达到 Quiesced 后先尝试 Prefill source-release notification 并上报一次普通 `finished_recving`、all-worker completion 后按顺序释放 Main 和 delayed NPU blocks；
- transfer failure：Indexer/Main phase 分类、任一 TP failure 后等待完整 terminal coverage、所有 TP `preserved_main_tokens=0`、full-sequence replay；
- aggregation：同一步 merge、跨 step exact rank coverage、相同 result duplicate 幂等、conflict/future/非法 rank fail closed、stale result 忽略、missing rank 无限期 pending；
- fused offload：`FUSED_D2H` range、preserved boundary、`D2H_COMPLETE` validity 推进、stale epoch/command rejection 和 D2H failure fail fast；
- negative contracts：不增加 connector outer retry、不检查 Prefill source TTL、不对 unquiesced operation 伪造 completion、不把 positional P/D compatibility 描述为 connector 已验证；
- 多请求交错：HOL request 暂时阻塞 younger request；完成、failure、preemption 和 cancellation 交错时 tracker 与 reservation 仍按 request 隔离；
- default isolation：DSA tests 运行后，普通 V1 的 metadata serialization、scheduler methods、transfer 和 completion tests 仍通过。

Phase B 通过才允许标记 `CPU/mock validated`。预计 Phase A 和 Phase B 合计增加约 700-1100 行 focused tests；NPU plan 约 200-350 行。完成两个阶段的测试实现和必要修复预计约 5-8 个工程日，不包含真实 NPU 运行时间。

## CPU/mock 执行要求

Phase A 和 Phase B 必须按照 workspace `AGENTS.md` 在 `liangjiahao` namespace 的专用长期运行 CPU-only UT Pod 中执行：

- 运行前记录 vLLM-Ascend branch、commit 和 dirty 状态；
- 使用 tar 加 `kubectl exec -n liangjiahao` 同步当前 checkout，不使用 hostPath；
- 命令行显式列出 pytest targets，禁用 bytecode 和 pytest cache；
- 不复用 Prefill/Decode serving Pod，不申请或挂载 NPU；
- 报告分别列出 Phase A 和 Phase B 的命令、结果、失败修复和最终 rerun，不能只给一个汇总 pass 数。

## NPU end-to-end 测试计划

当前只生成计划，不部署或执行 `P TP8/DP2 -> D TP2/DP8`。计划至少包含：

1. Preflight：测试计划按文档化部署前置条件核对 P/D immutable image digest、vLLM/vLLM-Ascend/Mooncake revisions、model/configuration fingerprint、topology、leader replica 假设、Host pool capacity 和 memory registration；任一不匹配时该 case 不得发流量。该检查属于测试执行步骤，不代表本 feature 实现 production deployment gate。
2. Happy path：短 partial-block prompt、多 block prompt、并发请求和持续 Decode，确认 Indexer destination 位于 Decode HBM、Main destination 位于每个 Decode TP local Swapped Host pool。
3. Correctness oracle：固定 prompts 与非分离 baseline 对比 output tokens 和约定的数值容差；选定 layer/block 使用 source/destination checksum 或等价 tensor oracle，避免仅靠最终文本掩盖 cache 错位。
4. Ordering/failure：通过可控 fault injection 证明 Indexer failure 不启动 Main，Main failure 不形成 receive-complete，并在所有 Decode TP terminal 后进入 full replay。
5. Lifecycle：reservation pressure 和 HOL、preemption 后 Main prefix reuse、cancellation drain-and-ack、`DONE_RECVING_MSG` best-effort Prefill source release，以及 unquiesced operation 的 ownership 隔离。
6. Isolation：同一配对 image 上关闭 `dsa_pd_offload`，执行普通 `MooncakeConnectorV1` PD regression。
7. Cleanup：请求完成或取消后，Main reservation、delayed NPU blocks、worker command state 和 scheduler trackers 回到基线；所有测试 workload 和 NPU allocation 按明确资源名清理。

计划中的每个 case 必须记录 prerequisite、命令/manifest、输入、oracle、成功条件、失败证据和 cleanup。未执行时统一标记 `planned / not run`，不得填写推测结果。

## 状态声明

测试状态使用以下含义：

```text
Phase A passed
  = 基本功能线通过，可以开始扩展 Phase B

CPU/mock validated
  = Phase A 和 Phase B 均已在规定 UT Pod 中执行通过

NPU E2E planned, not executed
  = 测试计划已完成，但没有真实 runtime 证据

NPU runtime validated
  = 未来真实执行全部 mandatory NPU cases 并保存证据
```

即使 Phase B 已通过，在 NPU plan 未真实执行前也不能声称实际 D2D/D2RH、NPU-addressable Host registration、fused kernel、leader replica ownership 或端到端数值正确性已经验证。本 feature 只维护 deployment compatibility preconditions 和测试证据要求，不实现或替代 production admission gate。

## 预计涉及文件

- `tests/ut/kv_offload/test_mooncake_dsa_metadata.py`：typed envelope、action/result validation 和 receive/replay/fused-D2H exact TP aggregation；
- `tests/ut/kv_offload/test_mooncake_dsa_connector.py`：opt-in/default isolation、positional mapping、ordering、failure、reservation 和 lifecycle；
- `tests/ut/kv_offload/test_sfa_kv_offload_scheduler.py`：admission、preemption 和 cleanup；
- `tests/ut/kv_offload/test_sfa_pd_cpu_offload_single_rank.py` 或新的 focused worker test：Swapped Main binding、fused D2H、epoch/command、worker-local quiesce 和 ordinary cancellation completion；
- feature-local NPU E2E test plan：只生成计划和 success criteria，不保存虚构的 run result。

测试文件名可在实现时按现有 test ownership 调整，但不应把大量 DSA state-machine cases 继续堆入已经较大的普通 V1 test class。

## 考虑过的方案

- 只完成 Phase A：反馈最快，但大量已经接受的 lifecycle correctness contract 没有自动化保护；不采用为最终门禁。
- Phase A 通过后扩展 Phase B：先快速打通基本功能，再系统验证边界；采用。
- 一开始直接实现完整 Phase B：最终覆盖相同，但首次反馈较慢，不利于定位数据面和状态机问题；不采用。
- 在 Phase B 上增加 property/model-based state-machine testing：覆盖更强，预计额外 3-5 个工程日；首版不采用，可作为后续测试增强。

## 结果

- 实现顺序固定为 Phase A -> 修复到全绿 -> Phase B -> 修复到全绿。
- Phase A 不是可跳过 Phase B 的 release waiver，也不能被表述为 CPU/mock 完整验收。
- Phase B 是当前可执行环境中的最终自动化正确性门禁。
- NPU E2E 只生成计划，状态始终与 static/CPU mock 结果分开。
- 本 ADR 关闭总设计中的最后一个待决策项；实现仍需按该顺序产出实际代码、测试和执行证据。
