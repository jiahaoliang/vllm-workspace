#!/usr/bin/env bash
set -euo pipefail
kubectl exec -n liangjiahao layerwise-performance-aisbench -c aisbench -- \
  chroot /performance-workspace/rootfs env TORCH_DEVICE_BACKEND_AUTOLOAD=0 \
  /client-tools/venv/bin/python -c '
import json
from urllib.request import Request, urlopen
request = Request(
    "http://mooncake-master-service:9003/api/v1/remove_all?force=true",
    data=b"",
    method="POST",
)
with urlopen(request, timeout=30) as response:
    assert response.status == 200
    body = json.loads(response.read())
assert body.get("success") is True, body
print(json.dumps(body, sort_keys=True))
'
