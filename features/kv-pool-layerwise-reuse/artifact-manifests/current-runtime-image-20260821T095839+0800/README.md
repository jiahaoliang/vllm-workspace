# Test 2 Profiling Runtime Image

This manifest records the independently loadable `linux/arm64` image that
freezes the exact Python runtime used by the accepted Test 2 Profiling + MSTX
diagnosis. The unchanged Mooncake/CANN/native dependencies are inherited from
the verified base image; this is a derived image, not a new native rebuild.

## Image Identity

- Reference: `docker.io/library/vllm-ascend:kv-pool-issue1-baf481c7-c97cef309-df3f74ed-mstx-20260821T095839`
- OCI manifest: `sha256:47a4ea30ce0e113669921723c044262f3ac98a24974da8b27b71efecf982f6d1`
- OCI config: `sha256:8c2d0ed9b22d0ad3debc06d54cba2da0572ab2ff0dcfa09cbb0c0157000a36c8`
- Platform: `linux/arm64`
- Unpacked size reported by containerd: `19.24 GB`
- Blob size reported by containerd: `6.799 GB`

## Source Identity

- vLLM: `baf481c7f0e84cd93705bcd4cdf42bcff03c3909`
- vLLM-Ascend: `c97cef309713dcf6c86412efd9c882b8425e28ce`
- Mooncake native: `df3f74ed8ebdb0c935554beea6299a9f11c723e2`
- Diagnostic overlay: `profile-mstx-20260819T184617+0800`
- Base image: `docker.io/library/vllm-ascend:kv-pool-layerwise-main-54503ece-a2-57d3c214e-df3f74ed-20260811T145302Z`
- Base digest: `sha256:f8592141757f7e9976898858863e12ccd051ac4a3fd6ade7591f78d9769517e3`

The image contains `/opt/vllm-layerwise/source-identity.json` and
`/opt/vllm-layerwise/source-overlay-sha256.txt`. Diagnostic environment
switches remain disabled by default.

## Local Archive

- Path: `/root/ljh/vllm-ascend-kv-pool-issue1-baf481c7-c97cef309-df3f74ed-mstx-20260821T095839.tar`
- Size: `6799441920` bytes
- SHA256: `30457cb466fe81a4434c947f9b9f96730cf3f12182953c8477ade594bf4d53b6`
- Persistence: local filesystem outside Git

Load with:

```bash
nerdctl -n k8s.io load -i \
  /root/ljh/vllm-ascend-kv-pool-issue1-baf481c7-c97cef309-df3f74ed-mstx-20260821T095839.tar
```

The archive passed `tar -tf`, whole-file SHA256, OCI descriptor digest/size
validation for the config, manifest, and all 22 layers, an isolated-namespace
reload, ARM64/OCI-label inspection, and an independent 6/6 embedded overlay
checksum replay. The final `k8s.io` tag resolves to the manifest above.
