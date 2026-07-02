Source: https://github.com/vllm-project/vllm/issues/33980
Captured At: 2026-07-02T17:47:19+08:00
Notes: Markdown snapshot of GitHub issue body via REST API.

# [RFC]: Sparse attention KV cache offloading to support longer sequence length

## Motivation.

In long sequence inference scenario, KV cache size has become one of the inference bottlenecks. To save GPU memory usage of KV cache and support longer sequence length, we have proposed a layerwise KV cache offloading approach in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)). However, during development we find out that the available offload layer number is limited by the loading speed: Based on a rough estimation, the loading time is $\frac{kv\\_cache\\_size}{bandwidth\\_dram2hbm}$, and since decoding is memory bound, the computing time can be approximated to $\frac{kv\\_cache\\_size}{bandwidth\\_hbm2cuda\\_core}$. So the ratio of $\frac{loading\\_time}{computing\\_time}$ should be approximated to $\frac{bandwidth\\_hbm2cuda\\_core}{bandwidth\\_dram2hbm}$, which is about 10x, matches [a test result](https://github.com/vllm-project/vllm/issues/33398#issuecomment-3831107982) based on llama-3.1-8B & NVIDIA H100. Thus the available offload layer number is limited to a lower range (< 10% of total layer number) in order to prevent addtional loading time overhead, limiting benefits from this feature.

While trying to use some high speed H2D channel and batch offloading to increase the dram2hbm bandwidth and shorten loading time, inspired by recent researches such as [SparseServe](https://arxiv.org/pdf/2509.24626), an LLM serving system designed for sparse attention optimization, we notice that KV cache offloading is especially efficient for sparse attention based model: Take [DeepSeek-V3.2](https://huggingface.co/deepseek-ai/DeepSeek-V3.2) as an example, although we still need to store full KV cache on GPU memory, only topk (2048) of them are needed in attention computation. So we propose another sparse attention KV cache offloading approach:

1. **Sparse KV cache offload:** For each layer, offload full KV cache to CPU, and only onload the topk KV cache needed for attention computation to GPU.

2. **Topk KV cache preload:** Although we can only get the topk index during each layer's forward pass, recent researches have shown the intra/inter-layer similarity of topk index distribution (Refer to [Topk KV preload](#topk-kv-preload) part for detail). This provides opportunity to optimize loading time by preloading: during previous layer's forward pass, we may use a former topk index (from previous layer or previous step) to preload behind layer's topk KV cache parallelly. Only a small part of cache miss KV cache needs to be onload sequentially again after getting the actual topk index, allow us to minimize the additional loading time overhead.

By offloading full KV cache to host and onloading the topk KV cache only, we can save most of the KV cache GPU memory usage. And since we only need to onload topk KV cache, the loading time should be much less than full attention, makes it more easy to be covered up by computing.

This sparse attention KV cache offloading approach is also orthogonal to our layerwise KV cache offloading approach in in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)), by combining both of them, we can reduce KV cache GPU memory usage up to $(1 - \frac{num\\_offload\\_layers}{num\\_layers}) \times \frac{index\\_topk}{max\\_model\\_len}$ of original size.

<div align='center'>
<img width="502" height="360" alt="Image" src="https://github.com/user-attachments/assets/28ecef71-7b8f-4c46-bacc-2761bc8e6882" />
</div>

## Proposed Change.

### KV cache management

<img width="1094" height="720" alt="Image" src="https://github.com/user-attachments/assets/b95bacdc-647f-4cb6-9898-b9a0a127e285" />

We plan to use a `topk_kv_buffer` on GPU with a fixed size of topk tokens to store the needed topk KV cache. In each step, we first allocate GPU blocks for new scheduled tokens and store new computed KV in GPU blocks (a), this is because we still need original GPU blocks to offload or transfer KV cache in PD disaggregation scenario. Then we select topk KV from new computed KV and history KV cache (maybe offloaded, onload if needed) and merge them into the `topk_kv_buffer`. Attention computation can be done based on the `topk_kv_buffer` (b). After each layer's forward pass, all the full blocks on GPU can be offloaded to host (c). Finally, in next step's scheduling, we free the offloaded full blocks from GPU block pool before allocating new blocks for new scheduled tokens (d).

We may need a new offload KV Cache manager inherits from `SingleTypeKVCacheManager` to manage the KV cache that needs offloading, since we may need to free some blocks before the whole request is freed. As for the k_cache needed by indexer, currently we plan to keep it on device so it can still use the original `FullAttentionManager`.

We also need some modification to current model_runner framework, such as supporting multiple attention type and mutiple block_table/slot_mapping in AttentionMetadata for one layer.

### Attention backend
Since the needed topk KV cache may exist in both device and host, we won't be able to use the original sparse attention kernel. Currently we plan to fetch device and host topk KV according to topk index manually and merge them into the `topk_kv_buffer`, then we can compute full attention based on it. We might need a new sparse + offload attention backend to implement this.

### Topk KV preload
Some recent researches have shown that the topk KV distribution has intra-layer similarity and inter-layer similarity. For example [FreeKV](https://arxiv.org/pdf/2505.13109) observed > 80% similarity between adjancent decoding steps (intra-layer similarity) across various models and tasks. Currently we are also trying to figure out the topk KV similarity between adjacent layers (inter-layer similarity).

These intra/inter-layer similarity provides opportunity to optimize loading time by preloading: We can compute previous layer's forward pass and preload behind layer's topk KV cache parallelly, only a small part of cache miss KV cache need to be onload sequentially again after getting the actual topk index, allow us to minimize the additional loading time overhead.

This topk KV preloading can be implemented similar to our layerwise KV cache offloading approach metioned in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)). We may start to preload all layers' topk KV at the beginning of model forward pass (in `start_load_kv`) according to the topk index from the previous decode step, or we can preload one layer's topk KV according to the topk index from its previous layer (in `save_kv_layer` of previous layer). We are now doing more experiments to find the best preload method.

## Feedback Period.

_No response_

## Co-Authors
@ader47 @520xie @luokui183 @wangxiaochao6 @pisceskkk @Pz1116 @fems14 @memfabric-dev @missever

## CC List.

@youkaichao @NickLucche @ApostaC @orozery @robertgshaw2-redhat 

## Any Other Things.

_No response_

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.
