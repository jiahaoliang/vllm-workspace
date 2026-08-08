# Mooncake Shared-Buffer Functional Validation Tracker

## Status

- Run ID: `20260808T042014Z`
- Status: `IN_PROGRESS`
- Namespace: `liangjiahao`
- Runtime node: `n1`
- Evidence root:
  `features/kv-pool-layerwise-reuse/evidence/shared-buffer-functional-20260808T042014Z`
- Performance claims: excluded

## Frozen Source

| Component | Identity |
| --- | --- |
| Control branch | `kv-pool-layerwise-reuse` |
| vLLM | `54503ecec0f3ac31e5ecfc5f28652e4cc42307b5` |
| vLLM-Ascend | `2770cd3ae66522c2eccb1c568889a55137836c0d` |
| Mooncake | `df3f74ed8ebdb0c935554beea6299a9f11c723e2` |
| Patched file SHA256 | `384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040` |
| Source remote equality | `0 0` |

## Frozen Image Plan

| Field | Value |
| --- | --- |
| Base image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Base manifest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Base config | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Platform | `linux/arm64` |
| Derived image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-2770cd3a-df3f74ed-20260808T042014Z-r1` |
| Derived manifest | `sha256:3f1f3d71941f66f006a2c2eb341d036007c3eb8c1abf4634559b69daba06f1a0` |
| Derived config | `sha256:cc66c08e15326c05d60e4fe5b3ac147a266282808d36d625c52d9e457ba88e77` |
| Patch layer | `sha256:e9233320b6ed9fcbc23e788b43773528ab1a340902414020f625b6f8ccd01da8` |
| Creation | Single Python-file patch followed by `nerdctl commit`; config/manifest-only label correction; not a native rebuild |

## Gate Tracker

| Gate | Status | Result / evidence |
| --- | --- | --- |
| TDD red | PASS | Producer returned `None`; pure consumer did not raise |
| Layerwise config focused UT | PASS | `20 passed` |
| Complete AscendStore CPU/mock | PASS | `504 passed` |
| Model-runner reuse targets | PASS | `2 passed` |
| Source Ruff | PASS | focused lint and format |
| Source compilation | PASS | `py_compile` |
| Source `git diff --check` | PASS | exit 0 |
| Source push equality | PASS | `0 0` |
| Deployment override contract | PASS | `16/16` local `unittest` contract; Pod rerun pending |
| Base image identity | PASS | platform, manifest, config and labels verified |
| Derived image identity/probe | PASS | `linux/arm64`; final SHA and role/config probes passed |
| Derived-image CPU/mock | PASS | `20` focused, `504` AscendStore, `2` model-runner, `85` deployment |
| No-reuse producer baseline | PENDING | |
| `kv_producer`, shared buffers 3 | PENDING | |
| `kv_both`, shared buffers 3 | PENDING | |
| 27-layer/5-slot/factor 5.400 proof | PENDING | |
| Descriptor merge proof | PENDING | |
| Range/save/load and output oracle | PENDING | |
| Final Master `0/0/0` | PENDING | |
| Root checksum replay | PENDING | |
| Performance handoff | WAITING | Must be the final ready transition |

## Execution Notes

- The retained `liangjiahao/vllm-ascend-ut` Pod was Ready on `n1`, had no NPU
  resource or hostPath, and had zero restarts at preflight.
- Only Prefill and the CPU UT Pod move to the derived image for this run.
  Mooncake Master stays on the native base image; pure Decode and stress
  resources are outside this functional run.
- The host Python environment lacks `pytest`; all required CPU/mock gates use
  the dedicated Kubernetes UT Pod.
- `nerdctl commit` did not preserve container labels. Final `-r1` changes only
  the OCI config and manifest descriptor; all 22 filesystem layer descriptors
  are exactly unchanged from the commit output. The superseded unlabeled tag
  and the exact patch container were removed after final inspect and probes.
- The combined worker/model-runner target retained one expected CPU-only
  failure before the worker method ran because `torch_npu.op_plugin.atb` is not
  installed. The corrected two-target model-runner descriptor gate passed. No
  driver was mounted and no production source was changed; the required
  27-layer/5-slot/5.400 memory proof remains a real-NPU startup-log gate.
- The final-image UT Pod UID is `129576b8-da11-4843-a8ad-48c9e37bcb1b`, its
  imageID is `sha256:cc66c08e15326c05d60e4fe5b3ac147a266282808d36d625c52d9e457ba88e77`,
  and it is Ready with zero restarts, no NPU request and no hostPath.
