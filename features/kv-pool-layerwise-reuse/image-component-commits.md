# Image Component Commits

Captured At: 2026-07-30T16:59:48+08:00

Source: `nerdctl -n k8s.io image inspect` against the local containerd image
store.

## `vllm-ascend:kv-pool-layerwise-v0.24.0-a2-session-api-20260729`

| Field | Value |
| --- | --- |
| Manifest digest | `sha256:bd3c7b2324d799c4a1f360bcbc8191cee2e4fa05c58f66bddc5d09bba9ee710f` |
| Config ID | `sha256:7e190798aee3cecae8bf3c91020ce2efab82d5900b290e2d659c724bf6ee313c` |
| Platform | `linux/arm64` |
| Created | `2026-07-29T05:01:49.756129162Z` |

| Component | Image label | Commit |
| --- | --- | --- |
| vLLM | `org.opencontainers.image.vllm.commit` | `ee0da84ab9e04ac7610e28580af62c365e898389` |
| vLLM Ascend | `org.opencontainers.image.vllm-ascend.commit` | `b5b65d9bbe325d009ad887fb87b8883b7ecee156` |
| Mooncake | `org.opencontainers.image.mooncake.commit` | `786c77ff7692bed58dd99971afef87d6b690cbe3` |

This is an immutable record of the components embedded in this image. The
current workspace checkout and `workspace.lock.json` may advance independently
and must not be used to infer this image's contents.
