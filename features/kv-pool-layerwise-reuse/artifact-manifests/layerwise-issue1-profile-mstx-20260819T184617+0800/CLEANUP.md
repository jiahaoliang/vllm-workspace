# Final Cleanup

- Final Mooncake metrics: `master_key_count=0`, `master_allocated_bytes=0`,
  `master_active_clients=0`.
- Prefill and Decode vLLM child processes were stopped before scale-down.
- `prefill-engine-deployment` and `decode-engine-deployment` are both at
  `replicas=0`.
- The complete live Deployment `.spec` for both roles equals its pre-run YAML
  snapshot.
- Temporary Pod template annotations for physical NPU 2,3 and 4,5 were removed.
- `profile-mstx-reserve-1` was deleted; physical NPU0 was released.
- Final `liangjiahao` Pod JSON contains no `huawei.com/Ascend910` request.
- `layerwise-runtime-config` has no diff from the pre-run snapshot.
- No namespace was deleted.
- Original `repos/vllm`, `repos/vllm-ascend`, and `repos/Mooncake` checkouts
  remain clean. Existing unrelated control-repo changes were preserved.
