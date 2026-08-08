Source: https://github.com/jiahaoliang/vllm-workspace/issues/1; https://api.github.com/repos/jiahaoliang/vllm-workspace/issues/1
Captured At: 2026-08-08T13:54:11+08:00
Notes: Verbatim first-party requirement snapshot retrieved successfully from the GitHub Issues API; no retrieval blocker. Later design-review refinements are intentionally not folded into the original issue text.

# jiahaoliang/vllm-workspace Issue #1: 性能测试

## Capture Metadata

- Number: `1`
- State: `open`
- Author: `jiahaoliang`
- Author association: `OWNER`
- Created: `2026-08-08T01:14:19Z`
- Updated: `2026-08-08T01:14:19Z`
- Comments at capture: `0`

The metadata and body below came from the repository owner's
[GitHub Issues API resource](https://api.github.com/repos/jiahaoliang/vllm-workspace/issues/1).

## Verbatim Issue Body

```text
# Cases
一. 第一个是测试的时候计算那边layerwise复用的能力关闭，他应该有个开关，把他关闭，我们纯测正常推理时候，原版vllm-ascend 按block存储，和我们现在按layerwise存储的性能对比。理论上layerwise的话可以有一部分和计算掩盖，block load的话得等block load好再开始计算。即以下两个对比
    1. use_layerwise： true, layerwise_num_shared_buffers: default
    2. use_layerwise： false, layerwise_num_shared_buffers: default
二. 第二个是把计算那边的layerwise复用的能力开启，去测整体不开他layer复用的开关+我们laywise offload开关作为基线，对比我们开启之后的性能。这个其实是更偏测试layerwise复用能力带来的提升，测试请求就是设置max token 为1，只测prefill这边，理论上prefill并发可以变大，tps可以提升。即以下三个对比
    1. use_layerwise： true, layerwise_num_shared_buffers: none（可以在测试一顺便测了）
    2. use_layerwise： false, layerwise_num_shared_buffers: none (可以在测试一顺便测了)
    3. use_layerwise： true, layerwise_num_shared_buffers: 3 (测试二新增)

测试工具： aisbench
```

## Requirement Extract

The issue defines two distinct comparisons:

1. With compute-side shared-buffer reuse disabled, compare original whole-block
   storage (`use_layerwise=false`) against layerwise storage
   (`use_layerwise=true`). The stated hypothesis is that layerwise transfer can
   overlap partly with compute, whereas whole-block load must complete before
   compute starts.
2. With `max token` set to one to focus on Prefill, reuse the two configurations
   above as baselines and add `use_layerwise=true` with
   `layerwise_num_shared_buffers=3`. The stated hypothesis is higher Prefill
   concurrency and TPS from compute-side layer reuse.

The issue explicitly selects AISBench as the test tool. It does not itself
specify topology, input lengths, repetition count, prompt construction,
statistical treatment, namespace, image workflow, or the exact interpretation
of `default` versus `none`; those are later design decisions and must not be
attributed to the original issue.
