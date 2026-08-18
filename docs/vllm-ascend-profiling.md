---
Source: https://ascendai.csdn.net/69dcb77572111d255bf8a98b.html
Captured At: 2026-08-18T15:16:14+08:00
Notes: 基于原文整理并按 workspace 当前 vLLM/vLLM-Ascend 接口改写；原文截图的有效信息已转写为文字，不保存图片资产。
Original Author: 昇腾实战派
Article Updated At: 2026-04-13T17:29:25+08:00
---

# vLLM-Ascend Profiling 使用指南

本文面向需要定位 vLLM-Ascend 推理性能问题的开发者，覆盖 Ascend
PyTorch Profiler 的采集、解析和 Timeline 阅读方法。Profiling 会明显增加
延迟、内存占用和落盘量，只应在受控的开发或性能诊断环境中使用，不应在生产
流量上长期启用。

本文以 2026-08-18 workspace 当前源码接口为准。原文中的截图没有复制到仓库；
截图展示的采集链路、源码配置、目录结构和 Timeline 含义均已整理为下文的文字、
表格和命令。

核对基线为 `workspace.lock.json` 中的 vLLM
`54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` 和 vLLM-Ascend
`57d3c214e642cdbb529400f0742d1a98a8d38708`。2026-08-18 当前 checkout 的
profiling 配置、wrapper、路由、benchmark 和测试文件与该基线 blob-identical。

## 当前版本的关键变化

原文基于较早的 vLLM-Ascend 实现。当前版本有以下不兼容变化：

| 原文做法 | 当前做法 |
| --- | --- |
| 设置 `VLLM_TORCH_PROFILER_DIR` | 在线服务使用 `--profiler-config`，离线推理使用 `profiler_config` |
| `python benchmarks/benchmark_serving.py` | 使用 `vllm bench serve` |
| `--random-range-ratio 1.0` 表示固定长度 | 当前参数范围是 `[0, 1)`；固定长度使用 `--random-range-ratio 0` |
| 直接修改 `worker.py` 或 `worker_v1.py` | 常规采集使用公共 `ProfilerConfig`；高级 NPU 参数当前仍由 `TorchNPUProfilerWrapper` 固定，不应临时修改已部署文件 |
| 修改 `EngineCore`，在初始化阶段强制启动 profiler | 当前没有对应的公共开关；请求期采集与图 capture 期采集必须区分，后者需要单独设计和验证源码改动 |

`VLLM_TORCH_PROFILER_DIR` 及同类 profiler 环境变量已经废弃。新脚本、manifest
和 runbook 不应继续使用它们。

## 采集链路

Ascend PyTorch Profiler 将一次推理的多个层级关联到同一条时间线上：

1. 框架层：Python 调用、PyTorch Module、ATen/torch_npu 算子和可选内存信息。
2. CANN 层：ACL、GE、Runtime 等 Host 侧下发过程。
3. NPU 层：Task Scheduler、AI Core、HCCL 和各个 device stream 上的 Kernel。
4. 分析层：Host 算子到 Device Kernel 的下发连线、通信/计算重叠和空闲区间。

因此，Timeline 中的“Python 调用较长”“CANN 下发较慢”和“NPU Kernel 较慢”是
不同问题。必须结合 Host 调用、下发连线和 Device stream 判断瓶颈，不能只看单层
耗时。

## 在线服务快速采集

### 1. 启动服务

使用 worker 进程可写、且便于从容器导出的绝对路径。默认先关闭 Module 层级和
内存采集，控制开销与文件大小：

```bash
MODEL_PATH=/path/to/model
mkdir -p /var/log/vllm-profile

vllm serve "$MODEL_PATH" \
  --host 0.0.0.0 \
  --port 8080 \
  --tensor-parallel-size 1 \
  --max-num-seqs 128 \
  --max-model-len 256 \
  --dtype bfloat16 \
  --profiler-config '{"profiler":"torch","torch_profiler_dir":"/var/log/vllm-profile","torch_profiler_with_stack":false,"torch_profiler_with_memory":false}'
```

`torch_profiler_dir` 的相对路径会被 vLLM 规范化为绝对路径，但容器和多进程场景
建议直接填写绝对路径。启用 profiler 后，服务才会注册 `/start_profile` 和
`/stop_profile`。这两个端点只应暴露在可信网络或本地 port-forward 中。

Ascend PyTorch Profiler 与 msmonitor daemon 不能同时启用。启动前应确认
`MSMONITOR_USE_DAEMON=0`，并确认 vLLM-Ascend additional config 中的
`msmonitor_use_daemon` 没有覆盖为 `true`。

### 2. 控制采集窗口

先完成模型启动和必要 warmup，再开始采集。只发送能复现问题的少量请求：

```bash
curl --fail-with-body -X POST http://127.0.0.1:8080/start_profile

curl --fail-with-body http://127.0.0.1:8080/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/path/to/model",
    "prompt": "San Francisco is a",
    "max_tokens": 7,
    "temperature": 0
  }'

curl --fail-with-body -X POST http://127.0.0.1:8080/stop_profile
```

`/stop_profile` 会等待 profiler 停止并触发落盘。Trace 较大时这个调用可能持续
数分钟，不要因 HTTP 请求耗时较长就杀死服务或删除 Pod。

### 3. 使用 benchmark 自动控制窗口

`--profile` 会在正式 benchmark 流量前后自动调用两个 profiler 端点。下面的
`random-range-ratio=0` 产生固定的输入、输出长度，便于对比不同运行：

```bash
MODEL_PATH=/path/to/model

vllm bench serve \
  --backend vllm \
  --base-url http://127.0.0.1:8080 \
  --model "$MODEL_PATH" \
  --dataset-name random \
  --random-input-len 128 \
  --random-output-len 4 \
  --random-range-ratio 0 \
  --ignore-eos \
  --num-warmups 1 \
  --num-prompts 4 \
  --max-concurrency 4 \
  --request-rate inf \
  --profile \
  --percentile-metrics ttft,tpot,itl,e2el
```

Profiler trace 本身不适合作为无扰动性能结果。正式吞吐或延迟数据应在关闭
profiling 后用相同模型、拓扑、输入输出长度和并发重新测量。

## 离线推理采集

离线 `LLM` 通过构造参数启用 profiler，不再写环境变量：

```python
import time

from vllm import LLM, SamplingParams


llm = LLM(
    model="/path/to/model",
    tensor_parallel_size=1,
    profiler_config={
        "profiler": "torch",
        "torch_profiler_dir": "/var/log/vllm-profile",
        "torch_profiler_with_stack": False,
        "torch_profiler_with_memory": False,
    },
)

prompts = [
    "Hello, my name is",
    "The president of the United States is",
    "The capital of France is",
    "The future of AI is",
]
sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=8)

llm.start_profile("offline")
try:
    outputs = llm.generate(prompts, sampling_params)
finally:
    llm.stop_profile()

# 多进程 worker 可能仍在完成后台落盘。
time.sleep(10)
```

`start_profile("offline")` 的可选前缀会进入各 rank 的 trace 名称，便于区分多次
采集。一次 profiler 对象重启时仍会沿用首次创建时的 trace 名称；需要完全独立的
命名和生命周期时，应重启 `LLM` 实例或服务。

## Kubernetes 场景

本 workspace 的测试 workload 必须使用 `liangjiahao` namespace。Pod 中的
`torch_profiler_dir` 必须对所有 worker 可写；如果目录位于临时文件系统，应在
删除 Pod 前导出结果。

通过本地 port-forward 控制采集：

```bash
POD_NAME=vllm-profile-server

kubectl -n liangjiahao port-forward "pod/${POD_NAME}" 18080:8080
```

在另一个终端调用：

```bash
curl --fail-with-body -X POST http://127.0.0.1:18080/start_profile
# 发送少量目标请求。
curl --fail-with-body -X POST http://127.0.0.1:18080/stop_profile
```

停止采集完成后检查并导出结果：

```bash
POD_NAME=vllm-profile-server
CONTAINER=vllm

kubectl -n liangjiahao exec "pod/${POD_NAME}" -c "$CONTAINER" -- \
  find /var/log/vllm-profile -maxdepth 2 -type d -name '*_ascend_pt'

kubectl -n liangjiahao cp -c "$CONTAINER" \
  "${POD_NAME}:/var/log/vllm-profile" \
  "./vllm-profile-${POD_NAME}"
```

不要复用 serving Pod 执行 CPU/mock unit tests，也不要为了 profiling 依赖当前
context 的 default namespace。

## 当前 `ProfilerConfig` 的实际语义

共享的 vLLM `ProfilerConfig` 包含多种平台参数，但当前 NPU wrapper 只消费其中
一部分。常用且在 Ascend serving 链路中有明确作用的配置如下：

| 字段 | 默认值 | 当前行为 |
| --- | --- | --- |
| `profiler` | `None` | 必须设为 `"torch"` 才能启用 Ascend PyTorch Profiler |
| `torch_profiler_dir` | 空 | `profiler="torch"` 时必填；本地路径会转换为绝对路径 |
| `torch_profiler_with_stack` | `true` | 在 NPU wrapper 中映射为 `with_modules`，用于 Module 层级；底层 `with_stack` 固定为 `false` |
| `torch_profiler_with_memory` | `false` | 传给 `profile_memory`；开启后显著增加开销和数据量 |
| `delay_iterations` | `0` | `/start_profile` 后延迟指定 worker step 再开始 |
| `max_iterations` | `0` | 按 worker step 限制采集窗口；`0` 表示不自动限制，仍应显式调用 stop |
| `ignore_frontend` | `false` | 设为 `true` 可避免同时采集 AsyncLLM frontend；使用 delay/limit 时通常更可控 |

当前 `WorkerProfiler` 在已记录 step 数量**超过** `max_iterations` 时触发自动 stop，
所以它不等同于精确的请求数上限。仍应保留显式 `/stop_profile`，并从 trace 中核对
实际覆盖的 step。

以下共享字段会被 `ProfilerConfig` 接受，但当前
`vllm_ascend.profiler.TorchNPUProfilerWrapper` 没有转发给 NPU worker profiler：

- `torch_profiler_record_shapes`
- `torch_profiler_with_flops`
- `torch_profiler_use_gzip`
- `torch_profiler_dump_cuda_time_total`
- `wait_iterations`、`warmup_iterations`、`active_iterations`

这些字段可能影响 vLLM frontend 或其他平台的 profiler，不能据此断言 NPU trace
已经包含 shape、FLOPs 或 schedule 数据。需要这些能力时，应先核对当前 wrapper
源码和测试，再通过正式配置扩展实现，不能只在启动命令中增加同名字段。

### 当前 NPU 固定配置

当前 `TorchNPUProfilerWrapper` 创建 `torch_npu.profiler.profile` 时使用：

| 配置 | 当前值 | 含义 |
| --- | --- | --- |
| `activities` | `CPU`、`NPU` | 同时采集 Host 和 Device 活动 |
| `with_stack` | `false` | 不采集完整 Python stack |
| `with_modules` | 来自 `torch_profiler_with_stack` | 采集 Module 层级关系 |
| `profile_memory` | 来自 `torch_profiler_with_memory` | 可选内存信息 |
| `export_type` | `Text` | 生成文本/CSV/JSON 类分析产物 |
| `profiler_level` | `Level1` | 在基础算子耗时上增加 AscendCL、HCCL 和 AI Core 指标 |
| `aic_metrics` | `PipeUtilization` | 采集计算与搬运流水线利用率 |
| `msprof_tx` | `false` | 默认不采集 MSTX 自定义打点 |
| `l2_cache` | `false` | 默认不采集 L2 cache 指标 |
| `op_attr` | `false` | 默认不采集算子属性 |
| `data_simplification` | `true` | 启用数据精简 |
| `record_op_args` | `false` | 默认不记录算子参数 |

原文介绍的 `ProfilerLevel.Level0/Level1/Level2`、`AiCMetrics`、L2 cache、DB
导出和 MSTX 都是 `torch_npu.profiler._ExperimentalConfig` 的能力，但
`_ExperimentalConfig` 是版本敏感的私有接口，而且这些值目前没有暴露为 vLLM
CLI 配置。若确需改变它们，应把需求实现为 vLLM-Ascend 源码变更，并为 wrapper
参数映射添加 unit tests；不要在运行中的容器内手改 Python 文件后把结果描述成
标准配置能力。

常见 AI Core 指标含义：

| `AiCMetrics` | 用途 |
| --- | --- |
| `AiCoreNone` | 不采集 AI Core 指标 |
| `PipeUtilization` | 计算单元与搬运单元的耗时占比 |
| `ArithmeticUtilization` | 各类计算指令占比 |
| `Memory` | 外部内存读写指令占比 |
| `MemoryL0` | L0 内存读写指令占比 |
| `ResourceConflictRatio` | 流水线队列冲突占比 |
| `MemoryUB` | Unified Buffer 相关指标 |
| `L2Cache` | L2 命中、缺失和重新分配相关指标 |

## 解析产物

停止采集后，每个 worker/rank 通常会在输出根目录下生成一个以
`_ascend_pt` 结尾的目录。多卡场景出现多个目录是正常现象，不能只保留 rank 0。

先定位原始目录：

```bash
find /var/log/vllm-profile -maxdepth 2 -type d -name '*_ascend_pt'
```

再对每个目录执行分析。不要在 profiler 尚未停止或仍在落盘时解析：

```bash
python3 -c 'from torch_npu.profiler.profiler import analyse; analyse("/var/log/vllm-profile/REPLACE_WITH_ASCEND_PT_DIR")'
```

典型目录包含原始 `FRAMEWORK`、`PROF_*`、`logs`、`profiler_info_*.json` 和
`profiler_metadata.json`，解析结果位于 `ASCEND_PROFILER_OUTPUT`。具体文件随
CANN、torch_npu 版本和采集开关变化，常见文件如下：

| 文件 | 用途 |
| --- | --- |
| `trace_view.json` | Chrome Trace 格式 Timeline，优先用 MindStudio Insight 查看 |
| `analysis.db` | 汇总分析数据库 |
| `ascend_pytorch_profiler_0.db` | Ascend PyTorch Profiler 数据库 |
| `api_statistic.csv` | API 调用统计 |
| `kernel_details.csv` | Device Kernel 明细、调用次数和耗时 |
| `operator_details.csv` | 框架算子明细 |
| `op_statistic.csv` | 算子聚合统计 |
| `step_trace_time.csv` | step 调度与阶段耗时 |
| `communication.json` / `communication_matrix.json` | 通信与 rank 关系；仅在采集到通信数据时出现 |

不要用“某个文件缺失”单独判断采集失败。先核对该文件是否需要对应 level、
export type、通信流量或其他采集开关。

## 阅读 Timeline

原文图片中的 Timeline 可以转写为以下阅读顺序：

1. 在 Python/Module 轨道定位一次请求、一次 model forward 或目标 Module。
2. 沿 ATen/torch_npu 算子向下查看 CANN 轨道，确认 Host 何时完成算子下发。
3. 通过 flow 连线定位对应的 NPU stream 和 Device Kernel。
4. 点击 Kernel 查看执行时长，并在 `kernel_details.csv` 中核对调用次数、平均耗时和总耗时。
5. 在 Overlap Analysis 中比较 Computing、Communication 与 Free 区间。

CPU 下发通常是异步的。可以把它理解为：CPU 依次准备并下发 `p1`、`p2`、
`p3`，NPU 在 stream 上稍后执行这些 Kernel；CPU 同时可能处理 dataloader、
调度或下一批请求。因此：

- CPU 区间长但 NPU 持续计算，不一定是瓶颈。
- NPU stream 出现空白，说明当时没有可执行 Kernel；应回看空白前最后一次下发、
  Host 同步、调度、数据准备或通信等待。
- Host 算子与 Device Kernel 之间没有 flow 连线，可能是采集窗口没有覆盖图 capture，
  不等于 Kernel 没有执行。
- 优化前应先区分计算慢、通信慢、Host 下发不足和显式同步，避免只按色块宽度猜测。

启用 `torch_profiler_with_stack=true` 后，当前 NPU wrapper 实际打开
`with_modules`。Timeline 会增加类似
`Model -> DecoderLayer -> Attention/MLP -> Linear/Norm` 的层级轨道，可进一步
建立 Module、框架 Op 和 Kernel 的关联。代价是更高的采集开销和更大的 trace。

## MSTX 与 Module 聚合分析

MSTX 用于给 Timeline 添加业务语义：

- `torch_npu.npu.mstx.mark` 标记瞬时事件，例如一次迭代开始。
- `range_start` / `range_end` 标记一个时间区间，例如 forward、all-reduce 或某个阶段。
- 不传 stream 时只记录 Host 区间；传入当前 NPU stream 时，可以关联 Host 与
  Device 侧活动。
- `mstx_domain_include` / `mstx_domain_exclude` 可用于筛选 domain，减少数据量。

但当前 workspace 的 NPU wrapper 固定 `msprof_tx=false`，所以仅在业务代码中
插入 MSTX 调用不会让当前默认 trace 获得这些事件。原文给出的“修改 worker、设置
`msprof_tx=True` 和 DB export，再全局替换 `nn.Module.__call__`”是旧版实验方案，
不应直接用于当前代码。

`msprof-analyze cluster -m module_statistic` 需要至少满足：

1. profiler 导出 DB 数据；
2. `msprof_tx=true`；
3. trace 中存在可识别的 `Module` domain range；
4. 使用版本与 CANN/torch_npu 产物格式兼容的 `msprof-analyze`。

当前默认的 `Text` export 和 `msprof_tx=false` 不满足这些前提。若实现了受支持的
配置扩展，Module 聚合结果通常包含以下列：

- `Parent Module` 与 `Module`：模型层级路径；
- `Op Name`：框架或 ACLNN 算子；
- `Kernel List`：该算子实际触发的 Device Kernel；
- `Total Kernel Duration`、`Avg Kernel Duration`、`Op Count`：总耗时、平均耗时和调用次数。

对当前版本，优先使用 `torch_profiler_with_stack=true` 获得 Module 层级，再结合
`operator_details.csv`、`kernel_details.csv` 和 Timeline flow 做关联。只有这些信息
不足时，才应开发 MSTX/DB 配置扩展。

## 图模式注意事项

服务启动完成后调用 `/start_profile` 只能覆盖请求期执行。如果 ACL graph 的
capture 发生在 `LLM` 或服务初始化期间，则请求期 trace 主要显示 graph replay，
可能缺少 capture 阶段的 Host-to-Device flow、算子 shape 或初始化事件，并出现
类似 `Fail to get acl to npu flow events` 的解析提示。

处理顺序应是：

1. 如果目标是请求期性能，保留图模式，只分析 replay 和实际请求窗口。
2. 如果目标是算子映射或 shape，先用 eager 模式做一个受控对照，确认问题是否只在图模式出现。
3. 如果必须分析 capture 本身，将“初始化前启动 profiler”实现为独立源码变更，验证启动、异常清理、多 rank 落盘和正常路径开销。

不要按原文截图在 `EngineCore.__init__` 中临时插入
`self.model_executor.profile(True)`，也不要省略正常的 stop/flush 生命周期。那种
改法既不是当前公共接口，也不能证明采集结果完整。

## 常见问题

### `/start_profile` 返回 404

服务启动时没有有效的 `--profiler-config`，因此路由未注册。检查启动日志和最终
渲染出的命令，不要再补 `VLLM_TORCH_PROFILER_DIR`。

### 报错 `Profiling is not enabled`

`profiler` 没有设为 `torch`，或 JSON/CLI 配置没有进入 worker。检查
`--profiler-config` 的引号和服务日志。

### 报错 msmonitor 与 torch profiler 冲突

同时启用了 `MSMONITOR_USE_DAEMON` 或 `msmonitor_use_daemon`。二者只能选择一个。

### stop 成功但找不到文件

检查 worker 对输出目录的写权限、容器内实际绝对路径、各 rank 日志，以及 stop
是否真正完成。Kubernetes 中还要确认检查的是 worker 所在容器，而不是 sidecar。

### Trace 太大或服务明显变慢

减少请求数量和输出长度，先关闭 `torch_profiler_with_stack` 与
`torch_profiler_with_memory`，必要时使用 `delay_iterations` 和
`max_iterations` 缩小窗口。Profiler trace 用于定位，不用于报告正式吞吐。

### 多次采集名称混在一起

当前 worker 首次创建 profiler 时确定 trace name，后续 start/stop 会复用对象。
需要严格隔离时重启服务，并为每次运行使用独立输出目录。

## 可比性清单

对比两个 trace 前至少记录：

- vLLM、vLLM-Ascend、torch_npu、CANN 的版本或 commit；
- 基础镜像 reference/digest 与 Python 覆盖文件 SHA256；
- 物理 NPU 分配、TP/DP/PP 拓扑和 rank；
- 模型、dtype、量化、eager/graph 模式和编译配置；
- 输入长度、输出长度、请求数、并发、request rate 和 warmup 语义；
- profiler 配置、输出目录、采集开始/结束时间和是否成功 flush。

只有保持这些条件一致，Timeline 或 CSV 的差异才有可解释性。

## 源码核对入口

更新 nested checkout 后，优先检查以下文件，而不是继续沿用本文中的默认值：

- `repos/vllm/vllm/config/profiler.py`：共享 `ProfilerConfig` 字段与校验；
- `repos/vllm/vllm/profiler/wrapper.py`：delay、limit 和通用 Torch profiler 行为；
- `repos/vllm/vllm/entrypoints/serve/profile/api_router.py`：在线 profiler 路由注册；
- `repos/vllm/vllm/benchmarks/serve.py`：`vllm bench serve --profile` 行为；
- `repos/vllm/examples/features/profiling/simple_profiling_offline.py`：离线示例；
- `repos/vllm-ascend/vllm_ascend/profiler/torch_npu_profiler.py`：NPU 实际参数映射；
- `repos/vllm-ascend/vllm_ascend/worker/worker.py`：worker start/stop 与 trace 命名；
- `repos/vllm-ascend/docs/source/developer_guide/performance_and_debug/service_profiling_guide.md`：上游 Ascend 服务采集指南。
