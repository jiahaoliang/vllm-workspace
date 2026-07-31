# Kubernetes UT Pod Design

## Objective

Provide one long-running, CPU-only Pod for command-driven vLLM-Ascend unit
tests. The Pod must not request an Ascend NPU or reuse a serving engine Pod.

## Runtime Contract

- Namespace: `liangjiahao`.
- Pod name: `vllm-ascend-ut`.
- Image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-14beaf16-20260731T064607Z-r1` with
  `imagePullPolicy: Never`, pinned to `n1` where the image is stored.
- The container runs `sleep infinity` and keeps an `emptyDir` checkout across
  test commands and container restarts.
- The Pod has CPU and memory resources only. It has no
  `huawei.com/Ascend910` request, NPU device, driver, `npu-smi`, model cache, or
  host workspace mount.
- CPU mocks are selected with `TORCH_DEVICE_BACKEND_AUTOLOAD=0`; the verified
  vLLM main development package selects the main compatibility lane naturally,
  with no `VLLM_VERSION` release override.

## Source And Command Flow

The host helper accepts an arbitrary command after `--`; it defines no default
pytest target. On every invocation it:

1. verifies the kube context, Pod identity, Running state, image, and absence
   of NPU resources and `hostPath` volumes;
2. acquires a Pod-side lock so source replacement and test execution cannot
   overlap;
3. streams the current `repos/vllm-ascend` checkout with tar over
   `kubectl exec`, excluding Git metadata and generated caches;
4. atomically replaces `/workspace/vllm-ascend` only after transfer succeeds;
5. requires clean source `14beaf161cca6f1e044e20529ca96c6554dbbe50`,
   then records the host commit, branch, dirty state, and sync time;
6. runs the supplied command from that snapshot with its path first on
   `PYTHONPATH`; and
7. releases the lock while leaving the Pod running.

## Validation

- Parse the manifest and assert every resource uses `liangjiahao`.
- Run `bash -n` on the helper and `git diff --check`.
- Apply only the namespace manifest and UT Pod manifest.
- Prove the live Pod has no NPU request/limit or `hostPath` volume.
- Sync the current checkout and run one named AscendStore unit test.
- Retain the Running Pod after the proof; cleanup deletes only the exact Pod,
  never the namespace.
