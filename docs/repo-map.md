# Repo Map

## repos/vllm

主 vLLM 仓库。`kv_offload` 开发中用于跟踪上游 RFC、KV cache 管理、scheduler、attention metadata 和 connector 框架相关改动。

## repos/vllm-ascend

Ascend 后端仓库。`kv_offload` 当前主要开发仓库，用于 Mooncake PD、SFA offload、Ascend attention backend 和 GLM sparse 路径相关实现。

## repos/Mooncake

Mooncake 传输与 KV cache 后端依赖仓库。默认只跟随 `main` 阅读和验证，不主动创建 feature branch。

## mooncake-learning 参考

历史学习资料位于 `C:\Users\l30034596\Documents\mooncake-learning`。本 workspace 只引用必要概念、路径或学习笔记，不迁移整个学习仓库。
