# 01 — 建立 Blockwise DSA opt-in control plane

**What to build:** 让部署工程师可以通过 `dsa_pd_offload=true` 在 `MooncakeConnectorV1` 内显式启用独立的 Blockwise DSA control plane，同时保证配置关闭时普通 V1 的 scheduler、metadata、worker、transfer 和 completion 行为不变。新 control plane 使用强类型 lifecycle command/result contract，并在启动或 metadata 边界拒绝本进程能够证明的 unsupported configuration 和 mode/type mismatch；跨 P/D deployment compatibility 只受文档化前置条件约束，不在本票实现 deployment system。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0002 — 保留 Decode pull 并使用 SFA Decode scheduler](../docs/adr/0002-retain-decode-pull-with-an-sfa-decode-scheduler.md)、[ADR 0017 — 使用独立的强类型 DSA metadata family](../docs/adr/0017-use-a-separate-typed-dsa-metadata-family.md)、[ADR 0018 — 使用嵌套 value object 组织 DSA step request](../docs/adr/0018-use-nested-value-objects-for-dsa-step-requests.md)、[ADR 0019 — 使用显式最小完备的 DSA step fields](../docs/adr/0019-use-minimal-complete-dsa-step-fields.md)、[ADR 0020 — 使用 lifecycle action 和 terminal local result](../docs/adr/0020-use-lifecycle-actions-and-terminal-local-results.md)、[ADR 0021 — 使用精确 TP coverage 和跨 step result 累积](../docs/adr/0021-use-exact-tp-coverage-and-cross-step-result-accumulation.md)

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] 配置关闭时继续构造和执行普通 V1 scheduler、metadata、worker 与 completion path，不构造或接受 DSA lifecycle metadata。
- [x] 配置开启时只接受 Prefill `kv_producer`、Decode `kv_consumer`、Decode `fused_overlap` 与 Mooncake SFA backend 的受支持组合，其他 role/mode 组合在启动时 fail closed。
- [x] 启动时拒绝 `P_TP < D_TP`、`P_TP % D_TP != 0`、Decode PP 大于 1 或 Decode `DCP * PCP != 1`，且不把 `P TP8/DP2 -> D TP2/DP8` 硬编码为唯一拓扑。
- [x] Decode scheduler-to-worker contract 使用 immutable request envelope，并将 remote source、destination ownership 和 lifecycle command 分成强类型 value objects。
- [x] Worker-to-scheduler typed contract 对 receive、fused D2H、replay 和 transfer failure 使用带 request、execution epoch、command sequence 和 local TP rank identity 的 terminal result，并实现合法的 action/result/failure-phase matrix；cancellation 不定义 typed `QUIESCED`。
- [x] Contract 只包含可跨进程传输的值，并通过集中 factory/validator 拒绝缺失字段、非法组合、冲突 command 和 mode/type mismatch。
- [x] 跨 P/D image、configuration、tuple ABI 和 leader replica compatibility 只记录为 feature deployment preconditions；本票不实现 manifest generator、release gate 或 admission controller。
- [x] Focused tests 覆盖 contract serialization、validator、同一步 duplicate/conflict typed aggregation、startup constraints 和 default V1 isolation。

## Answer

已在 vLLM-Ascend replacement commit `7401ae79c11d6ec0033ea3ac39085379a0bb81ef` 中完成。`mooncake_connector.py` 在既有 `MooncakeConnectorV1` public hooks 内实现 opt-in wiring，并使用 private `_MooncakeDsaDecodeScheduler(SFAPDCpuOffloadScheduler)` 管理 lifecycle；唯一新增的 production module `mooncake_dsa_metadata.py` 定义 immutable command/result contract、合法 matrix 和 same-step aggregation。未引入 standalone config、lifecycle、scheduler 或 worker subsystem。

Default V1 isolation、startup/async constraints、serialization、snapshot validation 和 aggregation 由 `test_mooncake_connector.py` 与 `test_mooncake_dsa_metadata.py` 覆盖。完整 replacement evidence 见 [CPU/mock validation report](../cpu-mock-validation-report.md)。
