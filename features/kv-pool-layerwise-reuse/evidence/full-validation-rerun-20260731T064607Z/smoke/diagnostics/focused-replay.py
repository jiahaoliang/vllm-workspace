from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx


MODEL = "vllm-ascend/DeepSeek-V2-Lite-W8A8"
PROXY_ENDPOINTS_URL = "http://vllm-proxy-service:8000/listEndPoints"
ARTIFACT_ROOT = Path("/tmp/layerwise-smoke")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_fixture(case: int) -> tuple[dict[str, object], dict[str, object]]:
    baseline_path = ARTIFACT_ROOT / f"empty-pool-baseline-{case}.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    choice = baseline["choices"][0]
    payload = {
        "model": MODEL,
        "prompt": choice["prompt_token_ids"],
        "max_tokens": 16,
        "temperature": 0,
        "seed": 2026072300 + case,
        "stream": False,
        "return_token_ids": True,
    }
    signature = {
        "text": choice["text"],
        "token_ids": choice["token_ids"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": baseline["usage"]["prompt_tokens"],
        "completion_tokens": baseline["usage"]["completion_tokens"],
    }
    return payload, signature


async def run_round(
    client: httpx.AsyncClient,
    decoder_url: str,
    cases: list[int],
    fixtures: dict[int, tuple[dict[str, object], dict[str, object]]],
) -> list[dict[str, object]]:
    responses = await asyncio.gather(
        *(client.post(decoder_url, json=fixtures[case][0]) for case in cases)
    )
    results: list[dict[str, object]] = []
    for case, response in zip(cases, responses, strict=True):
        body = response.json()
        choice = body["choices"][0]
        actual = {
            "text": choice.get("text"),
            "token_ids": choice.get("token_ids"),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": (body.get("usage") or {}).get("prompt_tokens"),
            "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
        }
        expected = fixtures[case][1]
        results.append(
            {
                "case": case,
                "http_status": response.status_code,
                "response_id": body.get("id"),
                "passed": response.status_code == 200 and actual == expected,
                "actual": actual,
                "expected": expected,
            }
        )
    return results


async def main() -> int:
    args = parse_args()
    cases = [int(value) for value in args.cases.split(",")]
    if (
        not cases
        or len(set(cases)) != len(cases)
        or any(case not in range(4) for case in cases)
    ):
        raise ValueError("--cases must be a unique comma-separated subset of 0,1,2,3")
    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")

    fixtures = {case: load_fixture(case) for case in cases}
    limits = httpx.Limits(
        max_connections=len(cases),
        max_keepalive_connections=len(cases),
    )
    rounds: list[dict[str, object]] = []
    async with httpx.AsyncClient(timeout=1200.0, limits=limits) as client:
        endpoints = (await client.get(PROXY_ENDPOINTS_URL)).json()
        decode_nodes = endpoints.get("decode_nodes") or []
        if len(decode_nodes) != 1:
            raise RuntimeError(f"expected one Decode endpoint, got {decode_nodes!r}")
        decoder_url = decode_nodes[0]["endpoint"] + "/v1/completions"
        for iteration in range(args.iterations):
            results = await run_round(client, decoder_url, cases, fixtures)
            rounds.append(
                {
                    "iteration": iteration,
                    "passed": all(result["passed"] for result in results),
                    "results": results,
                }
            )

    output = {
        "cases": cases,
        "iterations": args.iterations,
        "decoder_url": decoder_url,
        "passed": all(round_result["passed"] for round_result in rounds),
        "failed_rounds": sum(not round_result["passed"] for round_result in rounds),
        "rounds": rounds,
    }
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: output[key]
                for key in ("cases", "iterations", "passed", "failed_rounds")
            }
        )
    )
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
