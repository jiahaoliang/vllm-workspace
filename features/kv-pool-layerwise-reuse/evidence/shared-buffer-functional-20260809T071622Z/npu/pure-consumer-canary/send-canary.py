#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen


def main() -> int:
    input_tokens, output_tokens = map(int, sys.argv[1:])
    fixture = Path(
        f"/client-tools/fixtures/tokens-{input_tokens}-c64/warmup.jsonl"
    )
    prompt = json.loads(fixture.read_text(encoding="utf-8").splitlines()[0])[
        "question"
    ]
    payload = json.dumps(
        {
            "model": "vllm-ascend/DeepSeek-V2-Lite-W8A8",
            "prompt": prompt,
            "max_tokens": output_tokens,
            "temperature": 0,
            "ignore_eos": True,
            "stream": False,
        }
    ).encode()
    request = Request(
        "http://vllm-proxy-service:8000/v1/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=1800) as response:
        assert response.status == 200, response.status
        body = json.loads(response.read())
    usage = body["usage"]
    assert usage["prompt_tokens"] == input_tokens, usage
    assert usage["completion_tokens"] == output_tokens, usage
    assert len(body["choices"]) == 1, body
    print(json.dumps(body, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
