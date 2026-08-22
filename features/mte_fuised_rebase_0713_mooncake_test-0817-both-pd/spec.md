Status: ready-for-agent

## Problem Statement

客户希望在不启用 Prefill layerwise reuse 的情况下，让 Decode 继续使用 DSA sparse KV offload。当前穿刺实现已经打通 Indexer D2D 与 Main D2RH，但它建立在 layerwise connector、Prefill layerwise push 和穿刺式 SFA lifecycle 上，不能直接作为普通 request-level block transfer 的产品实现。

现有 `MooncakeConnectorV1` 已经提供 Decode-initiated、request-level、blockwise 的 PD 传输，但默认路径把普通 KV group 传入 Decode HBM，不理解 DSA 的两类 destination：Indexer cache 必须进入 Decode HBM，Main KV cache 必须进入每个 Decode TP process 自己的 Swapped Main pool。它也没有 Main lifetime reservation、Indexer-before-Main failure gate、execution epoch、request-level replay、两阶段 cancellation 或 rank-aware terminal result contract。

目标是在不修改 upstream vLLM core、不改变普通 `MooncakeConnectorV1` 默认行为的前提下，为 `MooncakeConnectorV1` 增加一个显式 opt-in 的 Blockwise DSA PD offload mode。该 mode 必须复用普通 V1 的 Decode-initiated block pull，迁移穿刺已经证明可行的 DSA memory placement 与 fused offload 能力，同时补齐穿刺代码没有正确处理的资源 ownership、failure、preemption、cancellation 和跨 TP completion 边界。

该能力涉及真实 NPU memory registration、D2D、D2RH 和 fused kernel，但当前环境没有足够算力部署首个目标拓扑。因此实现验证必须把 static、CPU/mock 和 NPU runtime evidence 分开，不能把 mock transfer 或未执行的计划描述成端到端通过。

## Solution

在 `MooncakeConnectorV1` 中增加由 `kv_connector_extra_config.dsa_pd_offload=true` 显式开启的 Blockwise DSA PD offload mode。关闭该配置时，普通 V1 scheduler、metadata、worker、transfer 和 completion 行为保持不变。

Prefill 保持普通 `MooncakeConnectorScheduler` 和 request-finish metadata flow，不分配 Decode Host blocks，不运行 SFA scheduler，也不使用 layerwise hooks。Prefill worker 在 opt-in mode 下暴露 Main K/V、Indexer 和可选 Indexer scale 的 positional source layout，并按固定 TP leader mapping 只由每个 leader 向对应 Decode TP 提供 payload。

Decode 使用继承现有 SFA scheduler 的 blockwise scheduler。它在请求 admission 前为请求的最大可能序列长度建立 Main lifetime reservation，分配当前 execution epoch 的 Indexer HBM ownership，并通过独立的强类型 DSA step metadata 向 worker 发布 remote source、current destination binding 和 lifecycle command。

每个 Decode TP worker 注册自己的 Indexer HBM 与 per-TP local Swapped Main pool。一次 `RECEIVE_REMOTE` command 在 worker 内先同步执行 Indexer D2D；只有 Indexer 成功才启动 Main D2RH。两条链路都成功后，该 TP 才产生 `RECEIVE_COMPLETE`。任一同步 transfer 最终失败时，worker 报告带明确 phase 的 `TRANSFER_FAILED`，而不是把局部成功伪装成 cache hit。

Worker result 使用 request、execution epoch、command sequence 和 local TP rank 作为 identity。Worker metadata 只合并同一个 engine step 的事实，Decode scheduler 跨 step 累积，并仅在当前 routed Decode DP replica 的精确 TP rank coverage 完整后推进 request lifecycle。

Transfer failure 后保留 Main reservation ownership，但所有 TP 的 Main validity 统一归零；所有 TP 都进入 Decode full-sequence replay。Preemption recovery 同样执行 Decode full-sequence compute replay以重建 Indexer，但在 ownership 和 validity 可证明时保留已有 Main prefix，避免重复 D2H。Cancellation 采用 drain-and-ack，只有 worker 已 quiesced 后 scheduler 才释放 Main reservation和 delayed NPU blocks。

P/D worker handshake 沿用穿刺 positional ABI，不增加 semantic role、protocol version、compatibility hash 或跨端 layout validation。部署系统必须在流量进入前保证 immutable image digest、model/configuration fingerprint、topology、tuple layout、memory placement 和 leader replica 一致，并禁止 mixed-version rolling upgrade。

实现先通过 Phase A quick validation 快速打通基本功能，再扩展 Phase B boundary validation。只有两个阶段都在规定的 CPU-only UT Pod 中执行通过，才能标记 `CPU/mock validated`。当前只生成以 `P TP8/DP2 -> D TP2/DP8` 为起点的 NPU E2E 计划，所有 case 保持 `planned / not run`，直到未来真实执行。

## User Stories

1. 作为部署 Blockwise DSA PD offload 的工程师，我希望通过一个显式配置开启新 mode，从而让默认 `MooncakeConnectorV1` 部署不受影响。
2. 作为普通 `MooncakeConnectorV1` 用户，我希望配置关闭时继续使用原有 metadata、scheduler、worker 和 completion path，从而避免 DSA 改动造成行为回归。
3. 作为 Prefill operator，我希望继续使用普通 request-level block transfer，从而不需要部署 Prefill layerwise reuse 或 layerwise push。
4. 作为 Prefill scheduler，我希望不持有 Decode Host block IDs，从而保持 P/D destination ownership 的职责边界。
5. 作为 Prefill worker，我希望按 positional tensor ABI 暴露 Main、Indexer 和可选 scale 的 registered layout，从而让 Decode 可以复用 Mooncake endpoint routing 拉取数据。
6. 作为部署系统，我希望在流量进入前核对 P/D immutable image digest 和 configuration fingerprint，从而阻止不兼容 positional ABI 配对。
7. 作为部署系统，我希望禁止 P/D mixed-version rolling upgrade，从而避免合法地址上的错误 tensor transfer silent success。
8. 作为部署工程师，我希望启动时拒绝非法 role 和 offload mode 组合，从而避免进程运行后才发现 unsupported configuration。
9. 作为部署工程师，我希望启动时拒绝 `P_TP < D_TP` 或 `P_TP % D_TP != 0`，从而保证固定 TP leader mapping 有定义。
10. 作为 Decode operator，我希望 Decode PP 必须为 1 且 `DCP * PCP == 1`，从而满足当前 scheduler 和 placement 的正确性约束。
11. 作为拓扑规划者，我希望 `P TP8/DP2 -> D TP2/DP8` 只是测试计划起点而非产品硬编码，从而允许其他满足约束的拓扑。
12. 作为 Decode TP worker，我希望只从自己的 fixed Prefill TP leader 拉取 payload，从而避免多个 Prefill rank 覆盖同一 destination。
13. 作为部署系统，我希望证明每个 leader 持有目标 Decode TP 所需的完整 Main 和 Indexer replica，从而让 leader-only transfer 不丢失 shard。
14. 作为 Decode scheduler，我希望在 remote receive 前为请求建立 Main lifetime reservation，从而保证请求 admission 后不会因 Decode 增长耗尽 Host capacity。
15. 作为 Decode scheduler，我希望按请求的 prompt 与最大输出长度计算 reservation capacity，从而只隔离请求真实可能使用的 Main blocks。
16. 作为 Decode operator，我希望 startup 证明最大合法请求能独占装入 Swapped Main pool，从而避免启动一个永远无法 admission 的配置。
17. 作为 Decode TP worker，我希望 scheduler block manager、runner-owned Host tensors 和 Mooncake registration range 容量一致，从而避免 block ID 越界或静默截断。
18. 作为等待 admission 的请求，我希望 capacity 暂时不足时留在 waiting queue，从而不回退到本地 Prefill或把资源不足扩大为 engine failure。
19. 作为队首大请求，我希望本 scheduling step 内后续 DSA 请求不能绕过我的 capacity miss，从而避免持续小请求导致 starvation。
20. 作为 scheduler operator，我希望 head-of-line gate 在下一个 scheduling step 重新判断，从而继续遵循 vLLM 当时的 FCFS 或 priority 顺序。
21. 作为 Decode worker，我希望 Main KV 写入当前 TP 自己的 local Swapped Main pool，从而保持 process-local ownership 和 fused offload consumption 模型。
22. 作为 Decode worker，我希望 Indexer cache 写入当前 execution epoch 的 HBM blocks，从而让 sparse selection 使用有效的 device-resident index。
23. 作为 remote-prefilled request，我希望 Indexer D2D 在 Main D2RH 之前完成，从而满足 ADXL memory type 分离和 Indexer hard gate。
24. 作为 remote-prefilled request，我希望 Indexer 失败时不启动 Main，从而不浪费 Main 链路或制造不受跟踪的 partial validity。
25. 作为 Decode scheduler，我希望只有所有 Decode TP 的 Indexer 和 Main 都成功后才接受 receive-complete，从而不把局部 TP success 当成完整 external KV。
26. 作为短 prompt 请求，我希望最后一个 partial block 按完整物理 block 传输，从而复用现有 blockwise transfer 和 fused offload layout。
27. 作为 Decode execution path，我希望使用已有 token state 限制 partial block 的有效范围，从而不引入第二套 `valid_token_count` 事实来源。
28. 作为 connector maintainer，我希望 Main K/V 使用相同 P/D block geometry，Indexer 只支持正整数 page ratio，从而把首版 mapping 限定为无需 split、merge 或 reformat 的布局。
29. 作为 connector maintainer，我希望 DSA scheduler-to-worker metadata 与普通 V1 metadata 分离，从而让非法 DSA 字段组合不会污染默认路径。
30. 作为 Decode worker，我希望通过嵌套的 source、destination ownership 和 lifecycle command 理解当前 step，从而不再依赖含义重载的扁平字段和 `getattr()`。
31. 作为 Decode scheduler，我希望独占完整 future Main reservation block list，从而让 worker 只能访问当前 command 已绑定的有序 Main prefix。
32. 作为 Decode worker，我希望通过 execution epoch 和 command sequence 拒绝 stale command，从而不让旧 Indexer ownership 或已释放 Main blocks被再次访问。
33. 作为 Decode scheduler，我希望 worker terminal result 携带 local TP rank，从而能检测重复、缺失和冲突 completion。
34. 作为 Decode scheduler，我希望相同完整 result 的重复上报幂等，从而允许正常的消息重复而不重复推进 lifecycle。
35. 作为 Decode scheduler，我希望冲突 result、future command 和非法 TP rank fail closed，从而避免协议损坏被 last-writer-wins 掩盖。
36. 作为 Decode scheduler，我希望 stale result 被记录并忽略，从而不恢复旧 ownership 或重复释放 reservation。
37. 作为 Decode scheduler，我希望缺失 TP result 时保持 request pending，从而不通过 timeout 或匿名计数推测 completion。
38. 作为发生 transfer failure 的请求，我希望在所有 TP terminal coverage 完整后进入 replay，从而避免 replay 与其他 TP 尚未结束的 DMA竞争。
39. 作为发生 transfer failure 的请求，我希望保留 Main reservation IDs 但把所有 TP 的 Main validity 归零，从而让 full replay确定性覆盖旧内容。
40. 作为发生 transfer failure 的请求，我希望只依赖 Mooncake internal retry，从而避免 binding retry 与 connector retry 形成乘法式嵌套提交。
41. 作为被 preempt 的请求，我希望保留 Main lifetime reservation，从而不让 preemption 破坏已经隔离的 Host capacity。
42. 作为被 preempt 的请求，我希望恢复时取得新的 Indexer HBM ownership，从而不使用已经由 vLLM core 释放的旧 blocks。
43. 作为被 preempt 的请求，我希望 Decode full-sequence replay 重建 Indexer，并复用可证明有效的 Main prefix，从而避免重复 Main D2H。
44. 作为性能工程师，我希望记录 replay token 数、复用 Main token 数和跳过的 D2H bytes，从而量化 full-sequence replay 的性能代价。
45. 作为被取消的请求，我希望 cancellation 后不再启动新的 receive、replay 或 fused D2H，从而限制取消后的额外资源访问。
46. 作为被取消的请求，我希望 worker quiesced 前 reservation 保持隔离，从而避免旧 operation 写入已分配给新请求的地址。
47. 作为 Decode scheduler，我希望在完整 TP `QUIESCED` 后 release-once，从而让重复 ack 和 late completion 不造成 double free。
48. 作为运行中的 Decode 请求，我希望 fused D2H success 推进 confirmed Main valid prefix，从而让后续 preemption recovery 能证明可复用范围。
49. 作为运行中的 Decode 请求，我希望 fused D2H failure 首版继续 fail fast，从而不通过不合法的 `finished_recving` channel 伪造 request-local recovery。
50. 作为 source lifetime 的维护者，我希望首版沿用普通 V1 的 Prefill hard TTL，从而不增加 launch grant、lease refresh 或跨节点时钟协议。
51. 作为系统 operator，我希望明确知道 TTL overrun 可能读取已复用地址并 silent success，从而不把 transport success 当作内容正确性证明。
52. 作为卡在同步 operation 中的请求，我希望 destination ownership 保持隔离，从而不在无法证明 quiesced 时被强制释放和复用。
53. 作为系统 operator，我希望首版不增加 feature-specific watchdog，并依赖 operation 返回、已有 process failure 或外部重启恢复，从而保持实现范围明确。
54. 作为测试工程师，我希望先运行 Phase A quick validation，从而尽早发现 mode wiring、mapping、ordering 和基本 lifecycle 错误。
55. 作为测试工程师，我希望 Phase A 通过后继续运行 Phase B boundary validation，从而验证 reservation、failure、preemption、cancellation 和 aggregation 边界。
56. 作为 reviewer，我希望只有 Phase A 与 Phase B 都通过时才标记 `CPU/mock validated`，从而不把 quick validation 冒充完整验收。
57. 作为 NPU 验证工程师，我希望获得以 `P TP8/DP2 -> D TP2/DP8` 为起点的可执行计划，从而在具备资源后验证真实 memory registration 和 transfer。
58. 作为 reviewer，我希望未执行的 NPU case 明确标记 `planned / not run`，从而不把测试计划描述为 runtime evidence。
59. 作为 NPU 验证工程师，我希望 correctness oracle 同时包含 baseline output 和选定 cache checksum 或等价 tensor oracle，从而降低最终文本掩盖 cache 错位的风险。
60. 作为测试 workload owner，我希望每个 NPU case 都包含 cleanup，从而释放 Pod、Mooncake session 和 NPU allocation，并保留可复核证据。

## Implementation Decisions

1. 新能力是 `MooncakeConnectorV1` 内的显式 opt-in mode，不增加新的公开 connector。配置关闭时不得构造或接受 DSA lifecycle metadata。
2. 首版只支持 Prefill `kv_producer`、Decode `kv_consumer` 的 PD disaggregation；Prefill 不启用 offload，Decode 使用 `fused_overlap` 和 Mooncake SFA backend。
3. Prefill scheduler 继续普通 `MooncakeConnectorScheduler`。Decode 使用继承现有 SFA CPU-offload scheduler 的 blockwise scheduler，负责 Main reservation、Indexer ownership、lifecycle command 和 cleanup。
4. Prefill worker 与 Decode worker 保留普通 V1 endpoint routing，但 DSA tensor layout 使用 layer-keyed positional arrays。Wire contract 不携带 semantic role、dtype、shape、memory kind、protocol version 或 compatibility hash。
5. Deployment compatibility gate 负责 P/D immutable image digest、dependency revisions、model/configuration fingerprint、tuple ABI、memory placement、topology和 leader replica compatibility。Connector 只检查本进程可以证明的结构、容量和 registration 事实。
6. 产品拓扑要求 `P_TP >= D_TP`、`P_TP % D_TP == 0`、Decode PP=1 和 Decode `DCP * PCP == 1`。`P TP8/DP2 -> D TP2/DP8` 只是测试计划起点。
7. Prefill TP 按 `P_TP / D_TP` 连续分组，每组第一个 rank 是对应 Decode TP 的唯一 payload source。Indexer、可选 scale、Main K 和 Main V 共用该 leader。
8. 首版不支持 multi-P shard assembly。Leader 必须持有完整 replica，该事实由 deployment gate 保证而非 handshake 证明。
9. Main K/V 的 P/D block geometry 必须相同。Indexer 只支持一个 Decode page 容纳正整数个 Prefill page；不支持非整数 ratio、反向 ratio 或 Main block split/merge/reformat。
10. Partial Main block 和 Indexer page 按完整物理长度传输。有效 token 范围来自现有 request token state，不新增 `valid_token_count` 或另一套 transfer range。
11. 每个 Decode TP process 拥有独立 Swapped Main pool并注册自己的 Main destination。Block ID 0 保留，scheduler capacity、runner Host tensor capacity 和 Mooncake registered range 必须一致。
12. Startup 必须证明一个 `max_model_len` 请求能够装入每个 TP 的可用 Swapped Main pool；不满足时 fail closed，而不是启动后永久等待。
13. Main reservation 按请求可能达到的最大序列长度一次性建立，分为 active prefix 和 future reserved suffix。Worker 只看到 stable reservation identity、总 capacity 和当前 command 已绑定的有序 Host prefix。
14. Reservation capacity 暂时不足时返回 waiting 结果，不分配 destination、不启动 transfer、不触发本地 Prefill。首版不增加 connector-local admission timeout。
15. Admission 使用 per-scheduling-step head-of-line gate。当前 step 首个 capacity miss 后，后续 DSA remote-prefill 请求本 step 不再尝试 reservation；下一 step 按 vLLM 当前顺序重新判断。
16. Decode-initiated pull 保持 request-level blockwise。一个 worker 的 `RECEIVE_REMOTE` command 内先执行 Indexer D2D，成功后再执行 Main D2RH，不增加两次 scheduler round 或跨 TP phase barrier。
17. Indexer final failure 不启动 local Main、不建立 Main validity，并产生 `TRANSFER_FAILED(INDEXER_D2D)`。Main final failure产生 `TRANSFER_FAILED(MAIN_D2RH)`。两条链路成功才产生 `RECEIVE_COMPLETE`。
18. 每个 transfer phase 在 Python connector 层只调用一次同步 Mooncake transfer，仅依赖 Mooncake binding internal retry，不增加 outer attempts、backoff 或 retry 配置。
19. Decode scheduler-to-worker 使用独立 DSA metadata family。Per-request envelope 包含顶层 request identity，以及嵌套的 remote source、destination ownership 和 lifecycle command。
20. Remote source描述 remote endpoint、remote request和 semantic Indexer/Main block IDs，不携带 raw address、TTL、lease 或 generation。Raw address由 positional handshake 与 local block mapping解析。
21. Destination ownership 描述 stable Main reservation identity/capacity、current bound Main Host prefix 和 current execution epoch 的 Indexer HBM IDs。Scheduler 是完整 future reservation block list 的唯一权威。
22. Lifecycle command携带 execution epoch、严格递增 command sequence、action、已有 token state、preserved Main boundary 和当前 fused D2H range。
23. Lifecycle actions固定为 `RECEIVE_REMOTE`、`FUSED_D2H`、`PREPARE_REPLAY` 和 `QUIESCE`。Indexer/Main是 receive command 内部 phases，不是 scheduler actions。
24. Terminal local results固定为 `RECEIVE_COMPLETE`、`D2H_COMPLETE`、`REPLAY_READY`、`QUIESCED` 和带 failure phase 的 `TRANSFER_FAILED`。
25. Result identity 是 request、execution epoch、command sequence 和 TP rank。相同 identity 的相同完整 result 幂等；冲突 result fail closed。
26. Worker metadata 只合并同一个 engine step 的 rank-aware facts。Decode scheduler 按 command identity 跨 step 累积，并要求当前 routed Decode DP replica 的 exact TP rank set。
27. Stale result记录并忽略；future result、非法 rank、action/result mismatch 和冲突 duplicate fail closed；缺失 rank无限期 pending，不增加 completion timeout。
28. Scheduler 在 vLLM core 消费 `finished_recving` 之前先解释 typed worker result。只有完整 receive、replay-ready 或 terminal quiesced transition 才在对应路径生成 `finished_recving`。
29. Transfer final failure 后等待当前 command 的全部 TP terminal results，然后向所有 TP 下发 `PREPARE_REPLAY`。Main reservation保留，但所有 TP 的 `preserved_main_tokens` 统一为 0。
30. Transfer-failure replay 从 token 0 执行 full-sequence forward，重建完整 Indexer 并重写完整 Main。局部成功 TP 不能复用远端 Main。
31. Preemption retire 当前 execution epoch并重新绑定 core 新分配的 Indexer HBM IDs。Main reservation跨 epoch 保留；可证明有效的 Main prefix在 compute replay 中不重复 D2H。
32. 无法证明 Main ownership、layout和validity 连续时，preemption replay同样把preserved boundary降为0并保守重写 Main。
33. Cancellation 采用两阶段 drain-and-ack。Admission 前可以立即结束；admission 后进入 cancel-pending，禁止新任务并保留 ownership，直到所有 worker quiesced。
34. 完整 TP `QUIESCED` 后 scheduler release-once Main reservation，并通过现有 delayed-block completion顺序让 core释放 NPU blocks。重复取消、ack和late completion均为no-op。
35. Fused D2H success产生 `D2H_COMPLETE`并推进 confirmed Main prefix。Fused D2H failure首版保持 worker/engine fail-fast，不伪造request-level connector recovery。
36. Transfer前检查local cancellation、execution epoch和destination ownership，但不检查 Prefill source age、remaining TTL或ownership。
37. 首版沿用普通 V1的Prefill source hard TTL和completion-based early release，不增加 launch grant、lease refresh、generation或clock-skew contract。
38. 对不返回或无法证明quiesced的operation，request和destination保持pending/隔离。不增加watchdog、fatal latch、reliable native cancel或timeout后强制释放。
39. 不修改 upstream vLLM core。实现复用 connector public hooks、`KVConnectorWorkerMetadata.aggregate()`、`KVConnectorOutput`和core已有的completion顺序。
40. 穿刺 connector只作为positional layout、memory registration、transfer ordering和SFA lifecycle的参考，不作为目标protocol，也不整体复制其状态管理。

## Testing Decisions

1. 测试优先验证跨组件可观察行为和ownership transition，不把private helper调用顺序当作主要正确性oracle。Mock只放在Mooncake transport、tensor/address、memory pool和vLLM scheduling artifacts等外部边界。
2. 主测试 seam 是 `MooncakeConnectorV1` public connector lifecycle。进程内 harness 从matched-token/admission开始，经过allocation、metadata、worker receive、worker result、scheduler output consumption和request finish，覆盖一个完整request lifecycle。
3. 主 seam 同时覆盖opt-in mode和default V1 isolation，避免只证明DSA路径能跑而漏掉普通connector回归。
4. 第一个支持 seam 是DSA metadata contract。直接验证immutable envelope、集中validator、action/result matrix、serialization-safe values、same-step aggregate和cross-step exact TP accumulation。
5. 第二个支持 seam 是SFA memory binding/data-plane adapter。通过现有registration、runner Host Main binding和fused-save接口，使用fake tensors和addresses验证Indexer HBM、Main Host、positional mapping、bound prefix和D2H range。
6. Phase A quick validation覆盖mode wiring、startup constraints、default isolation、positional local checks、leader/block mapping、partial physical block、single-request Indexer-to-Main ordering、Indexer/Main failure、最小receive/replay/release-once和focused static checks。
7. Phase A只是快速反馈门禁。Phase A失败时先修复基本路径；Phase A通过不能标记`CPU/mock validated`，也不能作为跳过Phase B的release waiver。
8. Phase B boundary validation覆盖full lifetime reservation、HOL admission、preemption和Indexer rebind、preserved Main D2H suppression、cancellation drain-and-ack、all-TP failure replay、duplicate/conflict/stale/future/missing result、multi-request interleaving和default V1 regression。
9. Phase B包含negative contract tests：不增加outer retry、不增加source TTL check、不对unquiesced operation伪造completion、不宣称positional handshake已证明P/D compatibility。
10. Phase A和Phase B必须在`liangjiahao` namespace的专用长期运行CPU-only UT Pod执行。同步当前checkout时使用tar加显式namespace的`kubectl exec`，不使用hostPath、不复用serving Pod、不申请NPU。
11. 每次CPU/mock运行记录source branch、commit和dirty状态；pytest命令显式列出targets并禁用bytecode和pytest cache。Phase A与Phase B分别报告命令、结果、修复和最终rerun。
12. 普通Mooncake tests提供scheduler hooks、block mapping、TP/CP/PP split、transport success/failure和default completion的prior art。
13. 穿刺Mooncake-to-DRAM tests提供positional address、D2D/D2RH SG list分离、Indexer page packing和TP port mapping的prior art，但其failure continuation不是目标行为。
14. 现有SFA scheduler和single-rank worker tests提供fused offload block allocation、Host binding、Indexer address和D2H range的prior art。
15. NPU E2E当前只生成计划。首个拓扑是`P TP8/DP2 -> D TP2/DP8`，但计划不得把它硬编码为产品唯一拓扑。
16. NPU plan包含deployment preflight、happy path、partial和multi-block、并发和reservation pressure、preemption、cancellation、ordering/failure injection、default V1 isolation与cleanup。
17. NPU correctness oracle同时使用固定prompt的baseline output比较与选定layer/block的checksum或等价tensor oracle，不能只靠最终文本判断cache placement。
18. 每个NPU case记录prerequisite、image/config identity、命令或manifest、输入、oracle、成功条件、失败证据和cleanup。未运行case统一标记`planned / not run`。
19. Static、CPU/mock和NPU runtime状态分别报告。只有未来真实执行全部mandatory NPU cases并保存证据后，才能标记`NPU runtime validated`。

## Out of Scope

- Prefill layerwise reuse、layerwise push、layerwise save/load hooks或完整实现vLLM issue #48203。
- 新增另一个公开Mooncake connector，或把目标实现继续建立在layerwise connector上。
- `kv_both`、P/D colocate、Decode pipeline parallel大于1，或Decode `DCP * PCP != 1`。
- `P_TP < D_TP`、`P_TP % D_TP != 0`、dynamic source selection、multi-P shard assembly或跨P DP replica混合tensor。
- Main block split/merge/reformat、非整数Indexer page ratio或Prefill Indexer page大于Decode page。
- Self-describing semantic tensor map、wire protocol version negotiation、compatibility hash或connector-side P/D layout proof。
- 独立P/D版本升级和mixed-version rolling upgrade支持。
- Host pool capacity multiplier、cross-process shared Main pool或独立destination-memory subsystem。
- Work-conserving reservation bypass；它保留为完成starvation、source TTL和cleanup设计后的优化方向。
- 修改upstream vLLM core，或复用当前只正确处理单KV group的core failure channel。
- Connector-level retry、retry attempts/backoff配置或Mooncake native retry语义修改。
- Prefill source launch grant、TTL检查、lease refresh、source generation或跨节点时钟协议。
- 对unquiesced operation增加watchdog、可靠cancel、fatal latch或有限时间自动恢复保证。
- Running request的fused D2H failure request-local recovery；首版继续fail fast。
- Preemption后重新从Prefill拉取Indexer/Main；它保留为降低full-sequence compute replay成本的后续性能优化。
- Property/model-based lifecycle testing；首版以deterministic Phase A/Phase B matrix为最终CPU/mock门禁。
- 在当前环境真实部署或执行`P TP8/DP2 -> D TP2/DP8` NPU E2E。
- 由connector实现生产deployment admission controller；deployment compatibility gate由部署系统承担，connector测试计划只规定所需证据。

## Further Notes

- 本能力是vLLM issue #48203的受限变体：Decode使用DSA offload，Prefill不使用layerwise reuse/offload。
- 设计中的“穿刺代码”是行为与风险参考，不是目标协议。穿刺已经证明Indexer D2D、Main D2RH和Swapped Main registration可以打通，但其preemption、cancellation、failure和completion状态不能直接复制。
- Positional ABI是明确接受的部署耦合。合法地址上的tuple、dtype、memory kind、page ratio或leader coverage错配可能silent success，full-sequence replay不能保证修复这类错误。
- Main lifetime reservation降低并发利用率，但把capacity failure移动到remote receive之前，并保证已admission请求后续增长不再动态申请Host blocks。
- Head-of-line admission可能暂时闲置可服务小请求的capacity。未来若重新引入work-conserving bypass，必须同时提供starvation bound、source TTL和cleanup闭环。
- Decode full-sequence replay可能显著增加preemption和failure恢复延迟。后续优先评估重新从Prefill拉取Indexer；在source lifetime、generation、rendezvous和幂等cleanup闭环前不启用。
- Source TTL overrun和unquiesced operation是首版明确接受的residual risks，不应通过扩大CPU/mock测试结论来隐藏。
- Phase A预计增加约350-600行focused tests并需要约2-4个工程日。Phase A和Phase B合计预计约700-1100行focused tests与5-8个工程日；这些估算不包含production实现、真实NPU运行和性能调优。
- 发布前的spec review已确认一个主connector lifecycle seam，以及DSA metadata contract和SFA memory binding两个支持seam。
