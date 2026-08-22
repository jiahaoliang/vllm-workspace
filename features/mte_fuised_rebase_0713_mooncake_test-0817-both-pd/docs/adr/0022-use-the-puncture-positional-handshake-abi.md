# 沿用穿刺 positional handshake ABI

状态：已接受

Blockwise DSA PD offload 的 P/D worker handshake 沿用穿刺 connector 的 positional ABI，不再建立 semantic tensor map，也不在 connector 内跨端校验 shape、dtype、memory kind、tuple role 或 layout compatibility。P/D 配对要求只作为部署文档中的 compatibility preconditions；本 feature 不实现 deployment admission controller。违反这些前置条件属于 unsupported configuration，可能显式失败，也可能产生无法由 connector 检测的 silent corruption。

本 ADR 取代 [ADR 0003](0003-advertise-semantic-tensor-map-in-handshake.md)，并取代 [ADR 0017](0017-use-a-separate-typed-dsa-metadata-family.md) 中“独立 versioned semantic handshake metadata”部分。ADR 0017 对 Decode scheduler-to-worker step metadata 和 worker-to-scheduler result metadata 的独立强类型要求继续有效。

## 穿刺代码怎么做

穿刺按 layer name 保存 positional metadata：

```python
class LayerMetadata:
    tensor_group_idx: list[int]
    kv_caches_base_addr: list[int]
    block_len: list[int]
    block_size_scale: list[int]


class MooncakeAgentMetadata:
    te_rpc_port: int
    layer_metadata: dict[str, LayerMetadata]
```

`register_kv_caches()` 按当前 local cache tuple 的迭代顺序 append group ID、base address、block length 和 scale。Wire payload 不携带 tensor semantic role、dtype、shape、memory kind、stride、protocol version 或 mode。收发双方使用同一份代码对 list position 和 layer-name/layer-index mapping 作相同解释。

穿刺 D 侧 Main/Indexer destination 也通过 positional arrays 发布：Main entry 保存 Host K/V 地址，Indexer entry 保存 Indexer 和可选 scale 地址。Transfer builder 根据当前代码中的位置、layer ID helper 和 list zip 生成 SG list，而不是从 wire metadata 读取 `MAIN_K`、`MAIN_V` 或 `INDEXER` enum。

## 普通 MooncakeConnectorV1 怎么做

普通 V1 的 `MooncakeAgentMetadata` 同样以 `kv_caches_base_addr`、`block_size_scale`、`block_lens` 和 `block_strides` 的平行数组表达 layout。它不携带 semantic role、dtype、shape 或 memory kind；remote `kv_group2layeridx` 不一致时当前实现只 warning，不建立强 compatibility contract。

目标 mode 继续使用普通 Mooncake 的 endpoint routing fields，例如 `engine_id`、`local_ip`、`handshake_port` 和 `te_rpc_port`，但 DSA layer layout 保持穿刺式 positional representation。可以定义 feature-local typed wrapper 以隔离 Python import boundary，但 wire semantics 不因此升级为 semantic protocol。

## Positional wire contract

首版 DSA handshake 的 layer payload 只要求：

```text
layer_metadata[layer_name]
  tensor_group_idx[]
  kv_caches_base_addr[]
  block_len[]
  block_size_scale[]
```

四个数组必须等长；数值必须能由本地注册逻辑使用。Main、Indexer 和可选 scale 的具体位置不由 wire schema 命名，而由当前 P/D image 中相同的 tuple adapter 和 transfer builder 共同解释。

Handshake 不增加：

- `protocol_version`、major/minor negotiation 或 compatibility hash；
- `semantic_role`、`memory_kind`、`dtype`、`shape` 或 registered-range descriptor；
- per-request block IDs、reservation IDs、token boundary 或 `valid_token_count`；
- P/D topology、leader replica proof 或 page-layout compatibility proof。

Local worker 仍可检查本进程能够直接证明的事实，例如数组等长、地址非零、block length/scale 为正、tensor registration 成功，以及 Decode Swapped Main pool 的容量、连续性和 NPU-addressable registration。Local check 不能被表述为跨 P/D compatibility validation。

## 文档化部署前置条件

部署和测试文档规定，配对的 P/D 运行环境在流量进入前必须满足：

- Prefill 和 Decode 使用同一个 immutable image digest，而不是只使用相同 mutable tag；
- image 内的 vLLM、vLLM Ascend、Mooncake native library 和 positional tuple adapter 来自同一组已验证 revision；
- P/D 使用相同 model revision、DSA/C8/offload flags、cache dtype、block size、layer layout 和 positional ABI；
- P/D topology 配置满足 `P_TP >= D_TP`、`P_TP % D_TP == 0`、Decode PP=1 和 `DCP * PCP == 1`；
- 固定 TP leader 确实持有对应 Decode TP 所需的完整 Main/Indexer replica；
- Decode Main destination 确实是当前 per-TP NPU-addressable Swapped Host pool，Indexer destination 确实是 HBM；
- 不进行 P/D mixed-version rolling upgrade；升级必须同时替换配对的 P/D deployment，或者先停止流量再切换；
- 部署记录或测试计划保存 image digest 和影响 ABI 的配置 fingerprint，作为一致性证据。

这些条件不是 connector handshake 校验项，也不是本 feature 的 production code 或 deployment deliverable。本工作只负责把条件、检查方法和所需证据写入 feature 文档与 NPU test plan；实际部署系统、manifest generator、release check 或 admission controller 的实现和选择均在范围外。缺少外部执行证据时只能声明 deployment compatibility 未验证，不能把文档约束描述成已实施的 gate。

## Failure boundary

Decode 仍在首次使用某个 remote endpoint 时通过普通 Mooncake flow 拉取 metadata，并在提交 Indexer D2D 前完成本地解析。但由于 wire payload 没有 version/mode/layout proof：

- 明显 decode error、缺失 layer、数组长度错误或 transfer API failure 可以 fail fast 或进入已经定义的 transfer-failure handling；
- tuple role、dtype、memory kind、page ratio 或 leader coverage 错配可能仍产生合法地址和成功 transfer status；
- 这类 silent mismatch 不触发 `TRANSFER_FAILED`，因此 ADR 0012 的 full-sequence replay 不能保证修复；
- connector 不声称支持独立 P/D upgrade、自动 compatibility negotiation 或 mismatch diagnosis。

## 考虑过的方案

- 完整 versioned semantic tensor map：能够在 transfer 前 fail closed，但增加 wire schema、adapter 和兼容矩阵；已由本 ADR 否决。
- 穿刺 positional ABI，并把完全同构写成部署前置约束：代码量较少，符合当前受控穿刺分支的使用方式，但约束执行在本 feature 范围外，并保留 silent corruption 风险；采用。
- 在 positional payload 外增加 compatibility hash：可以检测部分版本错配，但仍需定义稳定 canonical input 和 rollout contract；首版只记录部署前置约束，不采用。

## 结果

- Cache tuple/list position 成为 P/D 共享 ABI，不再只是 worker-local implementation detail。
- Handshake schema 不再是 self-describing semantic protocol，也不提供 wire-level version negotiation。
- Default `MooncakeConnectorV1` metadata 不增加 DSA optional semantic fields。
- Decode step metadata 仍使用 `main_block_ids` 和 `indexer_block_ids` 等强类型业务名称；只有从 block IDs 到 layer address arrays 的解析依赖 positional handshake ABI。
- 文档要求正确部署保存 image/config identity；本 feature 不生成或强制执行 production gate，缺少外部证据时不能声称 P/D layout compatibility 已验证。

## 预计实现影响

相对完整 semantic handshake，预计减少约 120-190 行 production Python 和 180-300 行 focused unit tests，节省约 2-4 个工程日。Positional handshake 本身预计增加约 70-130 行 production Python、120-220 行 focused tests，约 2-3 个工程日。预计涉及：

- `vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_connector.py`：构造和消费 DSA positional layer metadata，复用 endpoint routing；
- `vllm_ascend/distributed/kv_transfer/sfa_kv_offload/sfa_kv_offload_worker.py`：提供本地 Swapped Main binding 和 registration，保持 local safety checks；
- `tests/ut/kv_offload/test_mooncake_connector.py`：位置映射、数组长度、缺失 layer、Main/Indexer transfer list 和默认 V1 isolation；
- feature deployment constraints 文档或后续测试计划：规定配对 P/D image digest 与配置 fingerprint 的核对方法和证据；不实现 deployment system。
