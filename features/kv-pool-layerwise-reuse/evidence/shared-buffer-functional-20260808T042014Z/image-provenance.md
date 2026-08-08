# Derived Image Provenance

## Identity

| Field | Value |
| --- | --- |
| Run ID | `20260808T042014Z` |
| Base image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-45b2e785-df3f74ed-20260807T100722Z` |
| Base manifest | `sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351` |
| Base config | `sha256:eca977c2db3e6a45c331087298b0592cfa2af3794b39c06f03dc54219a7bba2b` |
| Patched source | vLLM-Ascend `2770cd3ae66522c2eccb1c568889a55137836c0d` |
| Patched path | `/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/layerwise_config.py` |
| Patched SHA256 | `384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040` |
| Final image | `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-2770cd3a-df3f74ed-20260808T042014Z-r1` |
| Final platform | `linux/arm64` |
| Final manifest | `sha256:3f1f3d71941f66f006a2c2eb341d036007c3eb8c1abf4634559b69daba06f1a0` |
| Final config | `sha256:cc66c08e15326c05d60e4fe5b3ac147a266282808d36d625c52d9e457ba88e77` |
| Patch layer | `sha256:e9233320b6ed9fcbc23e788b43773528ab1a340902414020f625b6f8ccd01da8` |
| Patch diff ID | `sha256:418ad546c06a558a10298d8bd1171555dee225ab73564fbd2731f6eb9a77dd93` |

## Construction

1. Verified the clean pushed source file and base image identity.
2. Created stopped container
   `kv-pool-layerwise-shared-buffer-patch-20260808T042014Z` with no network or
   device, copied only `layerwise_config.py`, copied it back out, and verified
   the exact SHA256.
3. `nerdctl diff` contained the target file and directory metadata entries; it
   contained no other changed regular file. Committed with `--pause=false`.
4. The installed `nerdctl 1.7.7` did not preserve container labels. A structured
   OCI correction updated only config labels and the manifest config
   descriptor. The original and final manifests have identical 22-element
   layer descriptor arrays.
5. Removed the exact patch container and the superseded unlabeled intermediate
   tag only after final inspect and probes passed. The native base and final
   `-r1` remain available.

This image is derived from a native ARM64 image. It is not a native rebuild.

## Required Labels

- `org.opencontainers.image.base.digest=sha256:411c381c0802547462636f897e73b986b01a3297577c7c3fe55c50d352c8e351`
- `org.opencontainers.image.patch.sha256=384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040`
- `org.opencontainers.image.patch.source-commit=2770cd3ae66522c2eccb1c568889a55137836c0d`
- `org.opencontainers.image.vllm-ascend.commit=2770cd3ae66522c2eccb1c568889a55137836c0d`
- `org.opencontainers.image.vllm.commit=54503ecec0f3ac31e5ecfc5f28652e4cc42307b5`
- `org.opencontainers.image.mooncake.commit=df3f74ed8ebdb0c935554beea6299a9f11c723e2`

## Probes

- Final image file SHA probe: `PASS`, exact
  `384fe5c2fd5deb785d151be15edc6c4ae0cd32cce75a2cb502aab802f9420040`.
- CPU-only isolated module probe: `PASS` for `kv_producer`, `kv_both`, and
  `kv_consumer + consumer_is_to_put=true`; pure consumer rejected.
- Config calculation: `27` layers, `3` shared buffers, `5` physical slots,
  logical memory factor `5.400`.
- Post-cleanup final image SHA probe: `PASS`.

The first direct-import probe is superseded: it stopped at the expected
CPU-only missing `libascend_hal.so` boundary before loading the patched module.
No NPU driver was mounted to make that probe pass.
