# 使用 nerdctl 构建 vLLM Ascend 镜像

Captured At: 2026-07-22T14:46:56+08:00

本文记录如何通过 `nerdctl` 调用 BuildKit Pod，使用 `Dockerfile.a2` 构建
vLLM Ascend layerwise KV pool 镜像。该流程不创建或修改 Kubernetes workload。

## 构建环境

当前环境通过以下变量指定 BuildKit 和 containerd namespace：

```bash
export BUILDKIT_HOST=kube-pod://buildkitd
export CONTAINERD_NAMESPACE=k8s.io
```

构建前可检查客户端和环境：

```bash
nerdctl --version
buildctl --version
printf 'BUILDKIT_HOST=%s\n' "$BUILDKIT_HOST"
printf 'CONTAINERD_NAMESPACE=%s\n' "$CONTAINERD_NAMESPACE"
```

`nerdctl build` 会调用本机的 `buildctl` 客户端连接 `buildkitd`。如果出现
`exec: "buildctl": executable file not found in $PATH`，应先确认 `buildctl` 已安装并在
`PATH` 中。

## 构建命令

在 workspace 根目录执行：

```bash
nerdctl -n k8s.io build \
  --progress=plain \
  -f features/kv-pool-layerwise-reuse/Dockerfile.a2 \
  -t vllm-ascend:kv-pool-layerwise-v0.24.0-a2 \
  features/kv-pool-layerwise-reuse
```

参数说明：

- `-n k8s.io`：选择 containerd 的 `k8s.io` namespace。
- `--progress=plain`：输出完整、适合保存和排查问题的构建日志。
- `-f`：指定名称不是默认 `Dockerfile` 的 `Dockerfile.a2`。
- `-t`：设置供后续命令和 Pod 引用的镜像名称及 tag。
- 最后的目录是 build context。当前 Dockerfile 没有 `COPY` 或 `ADD`，源码由构建阶段
  的 `git clone` 获取。

本次没有指定 `--platform`。BuildKit 使用 builder 的原生 ARM64 平台，最终镜像检查
结果为 `linux/arm64`。

## 本次构建结果

构建成功后，BuildKit 输出：

```text
Loaded image: docker.io/library/vllm-ascend:kv-pool-layerwise-v0.24.0-a2
```

containerd 中的实际镜像信息：

| Field | Value |
| --- | --- |
| Namespace | `k8s.io` |
| Image | `vllm-ascend:kv-pool-layerwise-v0.24.0-a2` |
| Platform | `linux/arm64` |
| Manifest digest | `sha256:155d929d8ffe8359cd1e9b7a4aa8e24df3460fb471341a731b9ead5f73c1262c` |
| Config ID | `sha256:f5f7031f1dc453e0390b5a2f889754902087f618f5e4f8e20678686443beb3a8` |
| Unpacked size | `19.21 GB` |
| Blob size | `6.797 GB` |

源码 labels 已核对：

| Component | Commit |
| --- | --- |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM Ascend | `663209fd6208a59a48742f75116345bf5f5281ec` |
| Mooncake | `74b0acf15bd6e41f0177b1e79c4a2eed39a58fa5` |

## 常用 nerdctl 命令

列出 `k8s.io` namespace 中的镜像：

```bash
nerdctl -n k8s.io images
nerdctl -n k8s.io images --digests vllm-ascend:kv-pool-layerwise-v0.24.0-a2
```

检查镜像配置、平台和 labels：

```bash
nerdctl -n k8s.io image inspect \
  vllm-ascend:kv-pool-layerwise-v0.24.0-a2
```

删除镜像引用：

```bash
nerdctl -n k8s.io rmi \
  vllm-ascend:kv-pool-layerwise-v0.24.0-a2
```

`rmi` 会删除指定 namespace 中的镜像引用。执行前应确认没有 Pod 或其他部署仍依赖该
tag；本次构建和验证没有执行 `rmi`。

## 镜像位置与使用限制

该镜像保存在 containerd 的 `k8s.io` image store 中，不对应 workspace 里的 tar 文件。
只有共享该 containerd image store 的节点能够直接使用它。多节点集群不会自动同步本地
镜像；其他节点需要通过 registry 分发，或另行执行 `nerdctl save`/`nerdctl load`。

由于 Ascend driver libraries 由目标节点和 device plugin 挂载，完整的动态导入和设备运行
验证应在实际 Ascend Pod 中完成。镜像构建阶段已经执行 Dockerfile 内置的 Mooncake API
静态检查。
