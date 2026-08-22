# 02 — 建立 positional data plane 与 Main lifetime reservation

**What to build:** 让合法的 Blockwise DSA 请求在 remote receive 前获得可寻址且容量有保证的 Decode destination：Prefill 暴露 positional source layout，Decode 为每个 TP 注册 Indexer HBM 和 local Swapped Main pool，并为请求完整生命周期建立 Main reservation；容量暂时不足时请求安全留在 waiting queue。

**Spec:** [Blockwise DSA PD offload spec](../spec.md)

**Decision basis:** [ADR 0001 — 使用 per-Decode-TP local Swapped Main pool](../docs/adr/0001-use-per-decode-tp-local-swapped-main-pools.md)、[ADR 0005 — 将 partial block 按完整物理 block 传输](../docs/adr/0005-transfer-partial-blocks-as-full-physical-blocks.md)、[ADR 0006 — 为请求完整生命周期预留 Main capacity](../docs/adr/0006-reserve-main-capacity-for-the-request-lifetime.md)、[ADR 0008 — 按 scheduling step 对 Main reservation 实施队首阻塞](../docs/adr/0008-use-per-step-head-of-line-reservation-admission.md)、[ADR 0022 — 沿用穿刺 positional handshake ABI](../docs/adr/0022-use-the-puncture-positional-handshake-abi.md)

**Blocked by:** 01 — 建立 Blockwise DSA opt-in control plane.

**Status:** ready-for-agent

- [ ] Prefill 继续使用普通 request-level `MooncakeConnectorScheduler` 和 request-finish flow，不分配 Decode Host blocks、不运行 SFA scheduler，也不使用 layerwise hooks。
- [ ] P/D worker 使用 layer-keyed positional arrays 表达 Main、Indexer 和可选 scale；本地检查数组等长、地址非零、长度/scale 为正、layer 完整和 registration 成功，但不宣称完成跨端 semantic compatibility validation。Image/configuration、tuple ABI、page layout 和 leader replica只作为文档化部署前置条件，本票不实现跨 deployment gate。
- [ ] 每个 Decode TP process 绑定并注册自己的 Indexer HBM 与 NPU-addressable local Swapped Main pool，保留 block ID 0。
- [ ] 启动时校验 scheduler block capacity、runner-owned Host tensor capacity 和 Mooncake registered range 一致，并证明一个 `max_model_len` 请求可以独占装入可用 Main pool。
- [ ] Main K/V 只接受相同 P/D block geometry；Indexer 只接受正整数 page ratio，不实现 split、merge 或 reformat。
- [ ] Admission 按请求可能达到的最大序列长度一次性分配 Main reservation，明确区分 current bound prefix、confirmed valid prefix 和 future reserved suffix。
- [ ] 容量不足时不分配 destination、不启动 transfer、不回退到本地 Prefill，并在当前 scheduling step 的首次 miss 后对后续 DSA remote-prefill 请求实施 head-of-line gate；下一 step 重新判断。
- [ ] Worker 只能访问当前 command 发布的有序 Main bound prefix；完整 reservation block list 与 release ownership 始终由 Decode scheduler 独占。
- [ ] Focused tests 覆盖 positional local checks、registration/capacity mismatch、最大请求 startup gate、reservation waiting/HOL、bound-prefix validation 和正常终态 release-once。
