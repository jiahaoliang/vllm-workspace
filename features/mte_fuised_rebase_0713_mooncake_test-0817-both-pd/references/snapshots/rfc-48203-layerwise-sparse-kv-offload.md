Source: https://github.com/vllm-project/vllm/issues/48203
Captured At: 2026-08-22T09:10:00+08:00
Notes: Markdown snapshot of GitHub issue body via REST API. Issue state at capture: open; last updated 2026-08-03T00:16:14Z.

# [RFC]: Layerwise and Sparse KV cache offloading to support longer sequence length

## Motivation.

In long sequence inference scenario, KV cache size has become one of the inference bottlenecks, arousing great interest in KV cache offloading. We also notice that KV cache offloading is especially efficient for sparse attention based model: Take [GLM-5.2](https://huggingface.co/zai-org/GLM-5.2) as an example, although we still need to store full KV cache, only topk (2048) of them are needed in sparse attention, this give us opportunity to save GPU memory usage by offloading the unused KV to host.

Based on the layerwise KV cache offloading approach we proposed in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)) and the sparse KV cache offloading approach we proposed in RFC ([#33980](https://github.com/vllm-project/vllm/issues/33980)), we now come up with a method that combines both these two approach, saving GPU memory usage in both prefill stage and decode stage.

1. **Layerwise KV cache offload & Prefill:** For prefill node (or prefill requests in pd-colocate), we use the layerwise KV cache offload. As explained in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)), multiple layers share one KV cache buffer, each layer fully onload its KV cache into this shared buffer before attention forward, and release it after attention is done.
   
   Although we need to onload & offload full KV cache of each layer, we can use multiple device KV cache buffer to parallel computing and loading, and prefill stage is long enough to cover the loading time. According to our experiments, 2-4 KV cache buffers are enough to overlap most of the loading time with computing.

<div align='center'>
<img width="400" alt="Image" src="https://github.com/user-attachments/assets/383b55ba-b6fe-457b-88b2-f73d0c1408c9" />
</div>

2. **Sparse KV cache offload & Decode:** For decode node (or decode requests in pd-colocate), we use the sparse KV cache offload. As explained in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)), all KV cache are offloaded to host, each layer only onload its needed topk KV cache during attention forward.

    Since we only onload the topk KV, loading time is short enough to be used in decode stage. We can further optimize loading time by cache reuse: each step we store the needed topk KV in a device buffer, during the next step we can reuse the KV which are already on device, only the cache miss part need to be onload from host. Based on DeepSeek-V3.2, we achieve 80%-90% cache hit rate by using a device buffer size of 2 * topk.

<div align='center'>
<img width="400" alt="Image" src="https://github.com/user-attachments/assets/6d91ff35-ea79-469d-b75b-1fa18d4b5261" />
</div>

Layerwise KV cache offloading can save KV cache GPU memory to $\frac{num\\_device\\_layers}{num\\_total\\_layers}$, and sparse KV cache offloading can save KV cache GPU memory usage to $\frac{indexer\\_cache\\_size}{kv\\_cache\\_size + indexer\\_cache\\_size}$ (Since indexer cache is not offloaded). By using these two offloading approach, we can save device memory usage in both prefill and decode. For example based on [GLM-5.2](https://huggingface.co/zai-org/GLM-5.2), we can save KV cache GPU memory usage up to 1/16 of original size, support up to 16x longer max_model_len or 16x larger batch_size.

## Proposed Change.

### KV cache management

To support the layerwise KV offload and sparse KV offload above, we need some modification on the KV cache management.

A. KV cache: Regardless of the model's layer number, we only allocate a fixed number of device KV cache buffers (currently we think 2-4 is enough). Needed for prefill.

B. Indexer cache: All the indexer caches are kept on device. Needed for both prefill and decode.

C. Topk buffer: A new device buffer to store the onloaded topk KV cache for each layer. Needed for decode. Topk buffer has a fixed size of n * topk, n == 1 meets the basic requirement of sparse attention, while we can also set n greater than 1 to improve cache hit rate.

D. CPU KV cache: Host buffer to store the offloaded full KV caches of all layers.

<div align='center'>
<img width="800" alt="Image" src="https://github.com/user-attachments/assets/5164db29-4e17-4902-89f3-caee8556fba1" />
</div>

Our first design use hybrid KV cache mode to manage the device KV cache and indexer cache, so that we can support KV offload in both PD disaggregate and PD co-locate scenario.

However, considering the implementation of hybrid KV cache mode is complex and may lead to too much intrusive modification, we decide to support PD disaggregate scenerio first, in this case P nodes only need to allocate KV cache & indexer cache in a fixed ratio of available memory, and D nodes only need to allocate indexer cache. We can implement this without hybrid KV cache support and less modification is needed in model_runner.

As for supporting KV offload in PD co-locate scenario, we might need more discussion in the future.

### Attention backend

Based on the layerwise/sparse offload motivation and the KV cache data structure above, we need some modification on the current sparse attention backend.

In prefill stage, we only use KV cache and indexer cache, the topk buffer is inactive. As explained in RFC ([#33398](https://github.com/vllm-project/vllm/issues/33398)), we can reuse the current KVConnector based KV offloading framework: make sure current layers' KV cache is already onloaded in `wait_for_layer_load` before attention forward, and start KV offload of current layer and KV onload of next layer in `save_kv_layer` after attention forward. Most of the other attention compute flow can keep unchanged.

<div align='center'>
<img width="800" alt="Image" src="https://github.com/user-attachments/assets/e719bc30-1fef-4b85-81e5-ea5c6a88577b" />
</div>

In decode stage, we only use indexer cache and topk buffer, the original device KV cache is inactive. Some of the original compute flow need modification: First, after PreAttn(qkv_proj, norm, rope, etc.), we need to offload the new KV to CPU KV cache instead of writing them to original GPU KV cache. Second, based on the topk_idx from indexer, we need to onload needed topk KV from CPU KV cache to the topk buffer. To speedup h2d, we also perform cache reuse here, topk KV which are already in topk buffer don't need to be onloaded again. Third, we perform sparse attention based on topk buffer instead of original KV cache.

<div align='center'>
<img width="800" alt="Image" src="https://github.com/user-attachments/assets/2485c81e-3d62-4974-a51e-996156cee72a" />
</div>

We might need a new sparse + offload attention backend to implement this.

### Offload backend

The offload backend should provide following KV transfer interface for offloading:

1. `d2h_block(src_block, dst_block)`
2. `h2d_block(src_block, dst_block)`
   
   These two block-level KV transfer interface are needed for layerwise offload in prefill stage.
3. `d2h_token(src_token, dst_token)`
4. `h2d_token(src_token, dst_token)`
   
   These two token-level KV transfer interface are needed for sparse offload in decode stage. Since this topk loading time can not be overlapped with computing, we have high requirements for the bandwidth and latency of these two interface. Due to the high sparsity of topk KV distribution, it might be challenging to implement these token-level KV transfer operators.

We are now trying to figure out if we can implement our layerwise & sparse KV offload based on existing offloading backends such as `OffloadingConnector` proposed in PR ([#22595](https://github.com/vllm-project/vllm/pull/22595)) or `SimpleCPUOffloadConnector` proposed in PR ([#37160](https://github.com/vllm-project/vllm/pull/37160)). We notice that there are some significant differences between our offload approach and the existing ones: existing offload approaches are based on block-level offload & onload, mainly aim to enlarge prefix cache pool and improve prefix cache hit rate, while ours is based on both block-level and token-level offload & onload, mainly aims to save device memory usage and support larger batch size or longer sequence length.

Due to the difference above, we may need to extend the existing offload backends. We may also consider to add a new offload backend for this sparse KV offload scenario if we find that the underlying data structure and loading process differ too large to combine together.

## Feedback Period.

_No response_

## Co-Authors.
@ader47 @Angazenn @gjc0824 @grandolantow @LCAIZJ @LookAround0301 @luokui183 @wangxiaochao6 @wlwen1995

## CC List.

@LCAIZJ @ivanium

## Any Other Things.

_No response_

## Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

