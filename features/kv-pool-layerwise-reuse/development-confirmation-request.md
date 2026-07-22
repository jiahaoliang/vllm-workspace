# Mooncake Layerwise KVPool 部署前开发确认请求

## 目标

计划在 Ascend A2 Kubernetes 环境验证以下路径：

```text
AscendStoreConnector
  + backend=mooncake
  + use_layerwise=true
  + PD disaggregation
  + chunked prefill
```

目标不是 `MooncakeLayerwiseConnector`，也不验证 `/v1/metaserver` P2P 路径。

## 当前环境

- 镜像：`vllm-ascend:kv-pool-layerwise-v0.24.0-a2`
- 镜像 digest：`sha256:661c9bc2c50c1b7253d6f9ec7905cc83f49908ef8cb1919108a5ea828c2cff8d`
- vLLM：`ee0da84ab9e04ac7610e28580af62c365e898389`
- vLLM-Ascend：`663209fd6208a59a48742f75116345bf5f5281ec`
- Mooncake：`74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5`
- Mooncake 七个 session/range API 已在镜像内确认存在。
- 本机已有完整 `Qwen/Qwen3-8B` 缓存，暂未发现 MLA 模型缓存。

## 问题一：Qwen3-8B 能否验证 Layerwise 数据路径？

设计与 implementation plan 包含 GQA block-key 及 GQA NPU E2E：

- `references/snapshots/design-mooncake-layerwise-gva-put.md` 第 2.3 节定义了 MLA 和 GQA key。
- `implementation-plan.md` 的约束声明首期支持 TP-only MLA/GQA。
- `implementation-plan.md` Task 5 要求 MLA、GQA 都执行 NPU E2E。

但当前实现存在以下静态证据：

1. 本机 Qwen3-8B 配置为 32 attention heads、8 KV heads，属于普通 GQA，不是 MLA。
2. `vllm_ascend/platform.py` 将非 MLA、非 sparse 模型映射到
   `vllm_ascend.attention.attention_v1.AscendAttentionBackend`。
3. `vllm_ascend/attention/attention_v1.py` 的 forward 中没有发现
   `wait_for_kv_layer_from_connector` 或 `maybe_save_kv_layer_to_connector` 调用。
4. `mla_v1.py`、`sfa_v1.py` 和 `dsa_v1.py` 明确包含上述逐层调用。
5. 当前 `docs/source/user_guide/feature_guide/layerwise_kv_pool.md` 也写明
   `attention_v1` 尚未集成 layerwise wait/save。

请明确回答：

- 当前 commit 是否声称支持 Qwen3-8B/GQA 的 layerwise KVPool？
- 如果支持，请给出
  `attention_v1 -> AscendStoreConnector.wait_for_layer_load/save_kv_layer`
  的实际调用链和代码位置。
- 如果不支持，implementation plan 中的“GQA 支持”和 GQA NPU E2E 是文档范围错误，
  还是当前分支遗漏了实现？
- 若确实遗漏，实现 GQA 支持最少需要修改哪些 attention 路径和测试？

## 问题二：本路径需要哪一种 Proxy？

Design snapshot 明确本功能不替代 `MooncakeLayerwiseConnector`，而是针对
`AscendStoreConnector + KVPool prefix cache`。

源码中 `/v1/metaserver` 参数、回调和访问逻辑位于
`vllm_ascend/distributed/kv_transfer/kv_p2p/mooncake_layerwise_connector.py`；standard
Kubernetes proxy 则从 prefiller 响应取得标准 `kv_transfer_params` 后转发给 decoder。

但是 `layerwise_kv_pool.md` 仍要求 dedicated layerwise proxy 和
`/v1/metaserver`，与上述设计边界和调用链冲突。

请确认：

- `AscendStoreConnector + backend=mooncake + kv_producer/kv_consumer` 是否可以使用
  standard disaggregated proxy？
- `/v1/metaserver` 是否只属于 `MooncakeLayerwiseConnector` 的 P2P 逐层推送协议？
- 当前 `layerwise_kv_pool.md` 的 proxy 说明是否继承自旧实现，需要修正？

## 问题三：完整 E2E 应使用什么模型和证据？

若 Qwen3-8B 当前不支持，请指定一个适合单张 64GB A2、TP=1 的 MLA 验证模型。
当前候选为 `deepseek-ai/DeepSeek-V2-Lite`。

同时请给出能够证明以下调用真实发生的正向证据：

- 每 chunk `batch_get_start`
- 每 chunk `batch_put_start`
- 每层 `batch_put_from_multi_buffer_ranges`
- 每层 `batch_get_into_multi_buffer_ranges`
- 每 chunk 完成后的 `batch_put_end`
- 仅 last chunk 执行的 `batch_get_end`
- 第二次相同 prefix 请求出现外部 KVPool hit

只验证请求成功或输出正确不够，因为它不能区分 layerwise ranged 路径、whole-key
路径和普通重计算。

## 期望回复格式

1. Qwen3-8B layerwise 支持：`支持 / 不支持 / 当前实现缺失`
2. 正确 proxy：`standard proxy / layerwise metaserver proxy`
3. 推荐 E2E 模型及最小启动参数
4. 可作为验收依据的日志、metric 或 trace
5. 如有实现缺口，列出必须先完成的代码与测试项
