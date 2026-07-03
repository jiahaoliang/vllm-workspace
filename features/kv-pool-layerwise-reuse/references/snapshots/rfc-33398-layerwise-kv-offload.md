Source: https://github.com/vllm-project/vllm/issues/33398
Captured At: 2026-07-02T17:47:19+08:00
Notes: Markdown snapshot of GitHub issue body via REST API.

# [RFC]: Layerwise KV cache offloading to support longer sequence length

## Motivation.

Currently, in vLLM v1 there are already some KV cache offload approaches such as `LMCacheConnector` proposed by PR ([#16625](https://github.com/vllm-project/vllm/pull/16625)) and `OffloadingConnector` proposed by RFC ([#19854](https://github.com/vllm-project/vllm/issues/19854)), which mainly aim to increase prefix cache hit rate by offloading KV cache of finished requests to CPU and onload them when cache hit, thus reduce ttft and improve throughput.

In long sequence inference scenario, the KV cache size has become one of the inference bottlenecks. Refer to existing KV cache offload approaches, we propose another layerwise KV cache offload approach, aims to reduce GPU memory usage of KV cache, thus improve the maximum model context length (max-model-len) we can support. The main idea of this approach is:

1. **Layerwise KV cache offload:** Offload KV cache of part of the layers to cpu, reduce GPU memory usage and support longer sequence. For each layer, we need to onload its KV cache before its forward pass, and offload its KV cache after its forward pass to make room for other layers behind.

2. **Asynchronous pipeline onload/offload:** Since we don't want KV cache onload/offload to block the original forward pass and thus improve ttft/tpot, we design an async pipeline onload/offload method. By preload KV cache of each layer before its forward pass, and parallel its forward pass with onload/offload of other layers, we are able to minimize the additional overhead of KV cache transmission.

<img width="868" height="538" alt="Image" src="https://github.com/user-attachments/assets/6745ac17-62ef-42d0-9abf-7e3120bed2f4" />

Inspired by [SparseServe](https://arxiv.org/pdf/2509.24626), an LLM serving system designed for sparse attention optimization, we also notice that this KV cache offloading approach is especially efficient for **sparse attention** based model: Take [DeepSeek-V3.2](https://huggingface.co/deepseek-ai/DeepSeek-V3.2) as an example, although we still need to store full KV cache on GPU memory, only topk (2048) of them are needed in attention computation. By offloading full KV cache to host and onloading the topk KV cache only, we can reduce GPU memory usage up to $\frac{offload\\_layer\\_number}{total\\_layer\\_number} \times \frac{index\\_topk}{max\\_model\\_len}$ of original size. And since we only need to onload topk KV cache, the onloading time should be much less than full attention, makes it more easy to be covered-up.

<div align='center'>
<img width="400" height="360" alt="Image" src="https://github.com/user-attachments/assets/5cb4753d-8973-487f-8d84-2893993c461f" />
</div>

The main difference between our layerwise KV cache offloading and existing KV offload approches is:
- The main purpose of existing KV offload approaches is to improve prefix cache hit rate: All KV cache of in-process request are kept on device, so it will not reduce the maximum GPU memory usage of KV cache. Only when a request is finished, it's KV cache is evicted from GPU and fully offload to CPU. The offloaded KV cache blocks only need to be onloaded when prefix cache hit. By offloading KV cache of finished requests instead of overwrite them directly, the prefix cache pool is enlarged and thus improve prefix cache hit rate.
- The main purpose of our layerwise KV offload approach is to reduce GPU memory usage: Only part of layers keep their KV cache on device, and other layers offload their KV cache to host so that we can save GPU memory usage. In each inference step, each offloaded layer needs to onload its KV cache for computation, and offload them again after computation to make room for layers behind. By offloading part of layers' KV cache, we can reduce KV cache GPU memory usage for the same input sequence length, or we can support longer sequence length with the same GPU memory size.
- Actually, our approach is more similar to the model weight offloading approach implemented in PR ([#6496](https://github.com/vllm-project/vllm/pull/6496)), the difference is we choose to offload KV cache instead of model weight, since KV cache GPU memory usage may be higher in long sequence inference scenario. And we also design an async pipeline onload/offload method instead of lazy onload each layer before its forward pass, so we are able to minimize the additional time overhead of offloading.

## Proposed Change.

### KV cache onload/offload:
We can reuse the current KVConnector based KV offloading framework to implement our layerwise KV cache offloading approach. We may add a new layerwise KV offload connector, implement our layerwise KV onloading in `wait_for_layer_load`, and KV offloading in `save_kv_layer`. By the existing `maybe_transfer_kv_layer` decorator, we are able to onload/offload each layer's KV cache before/after its forward pass. As for the offloading backend, we can reuse current `LMCache` backend or `CPUBackend` in RFC ([#19854](https://github.com/vllm-project/vllm/issues/19854)) for start.

### KV cache tensor sharing:
To achieve the goal of reduceing GPU memory usage by KV cache offloading, we find it a simple way to bind one KV cache tensor to multiple layers during `initialize_kv_cache`, and reuse the same KV cache tensor by KV offload/onload during computation. For example, for a model with two layers, we only allocate one KV cache tensor, and bind it to both two layers, so we can save GPU memory size of one layer's KV cache. In each inference step, we first onload layer0's KV cache to the KV cache tensor on GPU. After forward pass of layer0, we offload layer0's KV cache, and onload layer1's KV cache to overwrite the same KV cache tensor. Finally, we offload layer1's KV cache to make room for layer0's onload in next step.

We may reuse the current cross-layer KV sharing framework (`shared_kv_cache_layers`) to implement this part.

### Async pipeline loading design:
In order to minimize the additional time overhead of loading, we need to carefully design the onload/offload order of each layer, so that we can parallel loading with computing as mush as possible. Currently, according to the number of offload layers, our designs are as follows:

`num_layers`: Total layer number of the model.

`num_offload_layers`: Number of offloaded layers, 0 <= `num_offload_layers` <= `num_layers`.

#### Case 1: `num_offload_layers` == `num_layers` - 1
In this case, only one layer (which is in computing) is kept on device, so we must offload it after its forward pass, and onload the next layer before next layer's forward pass. The KV cache GPU memory usage can be minimized, but since there is only space for one layer's KV cache on device, the loading and computing of each layer must be serialized, so it will bring significant time overhead.

**Example 1**, `num_layers` = 12, `num_offload_layers` = 11:

<img width="1378" height="760" alt="Image" src="https://github.com/user-attachments/assets/ccbd4c3a-f19d-4e2d-9b2b-ce447e3de628" />

#### Case 2: `num_layers` // 2 <= `num_offload_layers` < `num_layers` - 1
In this case, since more than half of layers are offloaded, we still need to offload each layer after its forward pass and onload one other layer. However, since there are always at least two layers already on device, we are able to parallel loading of one layer with computing of another layer.

**Example 2**, `num_layers` = 12, `num_offload_layers` = 10:

<img width="1426" height="750" alt="Image" src="https://github.com/user-attachments/assets/eedeb79e-1ac9-430d-a5eb-46d445cf8afb" />

**Example 3**, `num_layers` = 12, `num_offload_layers` = 6:

<img width="1428" height="750" alt="Image" src="https://github.com/user-attachments/assets/a41acfbd-28a0-4626-b4c6-a9751fafd12b" />

By onloading/offloading each layer in a proper order, we are able to cover up most of the loading time. Note that in this case $time_{loading}$ (time of offload + time of onload per layer) need to be less than or equal to $time_{computing}$ (time of forward pass per layer), otherwise we can't fully cover it up.

#### Case 3: `num_offload_layers` < `num_layers` // 2
When $time_{loading}$ is greater than $time_{computing}$, we won't be able to fully cover it up if all layers need offload/onload. In this case, we can offload less than half of layers, so part of the layers can always keep on device, only the other part of layers need offload/onload. Each layer's loading can be parallel with more than one layers' computing, allow us to cover it up again.

**Example 4**, `num_layers` = 12, `num_offload_layers` = 3: Only 1+3=4 layers need to be offload/onload (+1 for the pipeline startup), and the other 8 layers can always keep on device. Each layer's loading can parallel with two other layers' computing, so the limitation can be relaxed to $time_{loading} <= 2 * time_{computing}$.

<img width="1498" height="988" alt="Image" src="https://github.com/user-attachments/assets/3c36ea7e-ab22-43c2-bceb-36759aea32e4" />

For the case that $time_{loading}$ is longer, we can futher decrease offload layer number, and keep more layers on device, so each layer's loading can be parallel with more layers' computing.

Although the examples above may seem complex, the async pipeline building can be basically independent of existing code: we only need an `onload_layer_map`, `onload_layer_map[i]` represents after layer i's forward pass, which layer behind needs to be onloaded. For the **Example 2** above, the `onload_layer_map` is {0: 2, 1: 3, 2: 4, 3: 5, ..., 8: 10, 9: 11, 10: None, 11: None}. We can calculate this map according to `num_layers` and `num_offload_layers`, and our OffloadConnector only needs to load the specified layer according to it.

## Feedback Period.

_No response_

## Co-Authors
@ader47 @520xie @luokui183 @wangxiaochao6 @pisceskkk @Pz1116 @fems14 @memfabric-dev @missever

## CC List.

@youkaichao @NickLucche @ApostaC @orozery 

## Any Other Things.

### Further Optimization
Some further optimizations temporarily placed in our todo list. We will continue to support these features after the basic kv cache offload feature is completed.

#### Better offload channel
Use communication channel with higher bandwidth instead of PCIe for KV cache offload and onload. Currently we plan to transfer KV cache between host and device through UB (UnifiedBus) on Ascend NPU backend, based on [MemFabric](https://gitcode.com/Ascend/memfabric_hybrid), which provides > 100 GB/s H2D bandwidth. Any suggestions of GPU offload backend are welcomed.

#### Batch offload
Individual layer operations generate excessive keys. During onload/offload, each block in every layer is assigned a unique key, and with N layers and M blocks per layer, this results in N $\times$ M keys. This large number of keys significantly degrades the performance of meta information lookup. A more efficient approach is to perform batch offloading, where blocks with identical block IDs across multiple layers are aggregated under unified keys. This reduces key generation from N $\times$ M to just M keys, greatly improving the lookup efficiency of meta information and overall system performance.

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.
