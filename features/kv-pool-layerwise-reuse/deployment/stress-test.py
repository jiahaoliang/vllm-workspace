#!/usr/bin/env python3
"""Deterministic workload driver for the multi-DP/TP KVPool stress run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


MODEL_PATH = "/root/.cache/modelscope/vllm-ascend/DeepSeek-V2-Lite-W8A8"
SERVED_MODEL = "vllm-ascend/DeepSeek-V2-Lite-W8A8"
BLOCK_SIZE = 128
TIMEOUT_SECONDS = 1800.0
SHARED_UNIT = "Shared stress validation prefix is identical across requests. "
INSTRUCTION = (
    "\nQuestion: Return exactly the private cache identity marker and no other words.\nAnswer:"
)
PREFILL_TRANSFER = {
    "do_remote_decode": True,
    "do_remote_prefill": False,
    "remote_engine_id": None,
    "remote_block_ids": None,
    "remote_host": None,
    "remote_port": None,
    "aborted_request": [],
}


@dataclass(frozen=True)
class Scenario:
    name: str
    case_count: int
    shared_blocks: int
    unique_blocks: int
    expected_keys: int
    seed_offset: int

    @property
    def cached_blocks(self) -> int:
        return self.shared_blocks + self.unique_blocks


SCENARIOS = {
    "s1": Scenario("s1", 4, 0, 127, 508, 0),
    "s2": Scenario("s2", 16, 48, 15, 288, 100),
    "s3": Scenario("s3", 4, 224, 31, 348, 200),
}


class ValidationError(RuntimeError):
    pass


def atomic_json(path: Path, value: Any, *, refuse_existing: bool = False) -> None:
    if refuse_existing and path.exists():
        raise ValidationError(f"refusing to overwrite raw artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(f"{path}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def repeat_tokens(tokenizer: Any, unit: str, target: int) -> list[int]:
    unit_tokens = tokenizer.encode(unit, add_special_tokens=False)
    if not unit_tokens:
        raise ValidationError(f"tokenizer returned no tokens for unit {unit!r}")
    repeat_count = max(1, (target + len(unit_tokens) - 1) // len(unit_tokens))
    encoded = tokenizer.encode(unit * repeat_count, add_special_tokens=False)
    while len(encoded) < target:
        repeat_count *= 2
        encoded = tokenizer.encode(unit * repeat_count, add_special_tokens=False)
    return encoded[:target]


def build_fixtures(tokenizer: Any, scenario: Scenario) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shared_target = scenario.shared_blocks * BLOCK_SIZE
    unique_target = scenario.unique_blocks * BLOCK_SIZE
    shared = repeat_tokens(tokenizer, SHARED_UNIT, shared_target) if shared_target else []
    tail = tokenizer.encode(INSTRUCTION, add_special_tokens=False)
    if not 1 <= len(tail) < BLOCK_SIZE:
        raise ValidationError(f"instruction token count must be in [1,127], got {len(tail)}")

    prompts: list[list[int]] = []
    markers: list[str] = []
    requests: list[dict[str, Any]] = []
    for index in range(scenario.case_count):
        marker = f"{scenario.name.upper()}_CASE_{index:02d}"
        unique_unit = f"{marker} private cache branch for case {index:02d}. "
        unique = repeat_tokens(tokenizer, unique_unit, unique_target)
        prompt = shared + unique + tail
        prompts.append(prompt)
        markers.append(marker)
        requests.append(
            {
                "model": SERVED_MODEL,
                "prompt": prompt,
                "max_tokens": 24,
                "temperature": 0,
                "seed": 2026072400 + scenario.seed_offset + index,
                "stream": False,
            }
        )

    cached_tokens = scenario.cached_blocks * BLOCK_SIZE
    expected_keys = scenario.shared_blocks + scenario.case_count * scenario.unique_blocks
    errors: list[str] = []
    if expected_keys != scenario.expected_keys:
        errors.append(f"expected key arithmetic is {expected_keys}, configured {scenario.expected_keys}")
    if any(len(prompt) != cached_tokens + len(tail) for prompt in prompts):
        errors.append("prompt length does not equal cached boundary plus tail")
    if not all(cached_tokens < len(prompt) < cached_tokens + BLOCK_SIZE for prompt in prompts):
        errors.append("prompt is not between cached boundary and next block boundary")
    if any(prompt[-len(tail) :] != tail for prompt in prompts):
        errors.append("prompt tails are not identical")
    decoded_tail = tokenizer.decode(tail, skip_special_tokens=False)
    for index, marker in enumerate(markers):
        decoded_cached = tokenizer.decode(prompts[index][:cached_tokens], skip_special_tokens=False)
        if marker not in decoded_cached:
            errors.append(f"{marker} is absent from its cached region")
        if marker in decoded_tail:
            errors.append(f"{marker} occurs in the common tail")
    for block in range(scenario.shared_blocks):
        values = {tuple(prompt[block * BLOCK_SIZE : (block + 1) * BLOCK_SIZE]) for prompt in prompts}
        if len(values) != 1:
            errors.append(f"shared block {block} is not identical")
    for block in range(scenario.shared_blocks, scenario.cached_blocks):
        values = {tuple(prompt[block * BLOCK_SIZE : (block + 1) * BLOCK_SIZE]) for prompt in prompts}
        if len(values) != scenario.case_count:
            errors.append(f"unique block {block} has {len(values)} variants")
    if errors:
        raise ValidationError("; ".join(errors))

    fixture = {
        "schema_version": 1,
        "scenario": scenario.name,
        "definition": asdict(scenario),
        "block_size": BLOCK_SIZE,
        "cached_blocks": scenario.cached_blocks,
        "cached_boundary_tokens": cached_tokens,
        "tail_tokens": len(tail),
        "prompt_tokens": [len(prompt) for prompt in prompts],
        "markers": markers,
        "seeds": [request["seed"] for request in requests],
        "request_ids": {
            "baseline": [f"stress-{scenario.name}-baseline-{i}" for i in range(scenario.case_count)],
            "pinned": [f"stress-{scenario.name}-pinned-{i}" for i in range(scenario.case_count)],
            "proxy": [f"stress-{scenario.name}-proxy-{i}" for i in range(scenario.case_count)],
        },
        "request_files": [f"requests/case-{i:02d}.json" for i in range(scenario.case_count)],
        "expected_key_count": scenario.expected_keys,
    }
    return requests, fixture


def contains_subsequence(values: list[int], needle: list[int]) -> bool:
    if not needle:
        return False
    return any(values[index : index + len(needle)] == needle for index in range(len(values) - len(needle) + 1))


def response_signature(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices") or []
    if not choices:
        raise ValidationError("response body has no choices")
    choice = choices[0]
    usage = body.get("usage") or {}
    return {
        "text": choice.get("text"),
        "finish_reason": choice.get("finish_reason"),
        "stop_reason": choice.get("stop_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


def normalized_text(value: Any) -> str:
    return " ".join((value or "").split())


def isolation(text: Any, own: str, markers: Iterable[str]) -> tuple[bool, list[str]]:
    value = text or ""
    foreign = [marker for marker in markers if marker != own and marker in value]
    return own in value and not foreign, foreign


def metric_value(text: str, name: str) -> int:
    for line in text.splitlines():
        if line.startswith(f"{name} "):
            value = float(line.split(None, 1)[1])
            if not value.is_integer():
                raise ValidationError(f"metric {name} is not an integer: {value}")
            return int(value)
    raise ValidationError(f"metric is missing: {name}")


def state_path(output: Path) -> Path:
    return output / "scenario-state.json"


def update_state(output: Path, action: str, detail: Any) -> None:
    path = state_path(output)
    state = load_json(path) if path.exists() else {"schema_version": 1, "actions": {}}
    if action in state["actions"]:
        raise ValidationError(f"action is already recorded: {action}")
    state["actions"][action] = detail
    atomic_json(path, state)


def prepare(args: argparse.Namespace) -> None:
    from transformers import AutoTokenizer

    output = args.output
    if any(output.iterdir()):
        raise ValidationError(f"prepare requires an empty scenario directory: {output}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    requests, fixture = build_fixtures(tokenizer, SCENARIOS[args.scenario])
    for index, request in enumerate(requests):
        atomic_json(output / "requests" / f"case-{index:02d}.json", request, refuse_existing=True)
    atomic_json(output / "fixture.json", fixture, refuse_existing=True)
    update_state(output, "prepare", {"fixture": "fixture.json"})


async def discover_endpoints(client: Any, proxy_base_url: str) -> tuple[str, str, dict[str, Any]]:
    response = await client.get(f"{proxy_base_url.rstrip('/')}/listEndPoints")
    response.raise_for_status()
    body = response.json()
    prefill = body.get("prefill_nodes") or []
    decode = body.get("decode_nodes") or []
    if len(prefill) != 1 or len(decode) != 1:
        raise ValidationError(f"expected one endpoint per role, got {body}")
    return prefill[0]["endpoint"], decode[0]["endpoint"], body


async def post_one(client: Any, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    started = time.time()
    try:
        response = await client.post(url, json=payload, headers=headers)
        try:
            body: Any = response.json()
        except Exception:
            body = response.text
        return {"status_code": response.status_code, "body": body, "error": None, "elapsed_seconds": time.time() - started}
    except Exception as exc:
        return {"status_code": None, "body": None, "error": f"{type(exc).__name__}: {exc}", "elapsed_seconds": time.time() - started}


def validate_raw(raw: dict[str, Any], name: str) -> dict[str, Any]:
    if raw.get("error"):
        raise ValidationError(f"{name}: {raw['error']}")
    if raw.get("status_code") != 200:
        raise ValidationError(f"{name}: HTTP {raw.get('status_code')}")
    if not isinstance(raw.get("body"), dict) or not raw["body"].get("choices"):
        raise ValidationError(f"{name}: response body has no choices")
    return raw["body"]


def requests_for(output: Path) -> list[dict[str, Any]]:
    fixture = load_json(output / "fixture.json")
    return [load_json(output / path) for path in fixture["request_files"]]


async def baseline_async(args: argparse.Namespace) -> None:
    import httpx

    requests = requests_for(args.output)
    fixture = load_json(args.output / "fixture.json")
    limits = httpx.Limits(max_connections=len(requests), max_keepalive_connections=len(requests))
    started = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, limits=limits) as client:
        _, decode, endpoints = await discover_endpoints(client, args.proxy_base_url)
        atomic_json(args.output / "baseline" / "proxy-endpoints.json", endpoints, refuse_existing=True)
        calls = [post_one(client, f"{decode}/v1/completions", payload, {"X-Request-Id": fixture["request_ids"]["baseline"][i], "X-data-parallel-rank": "0"}) for i, payload in enumerate(requests)]
        raws = await asyncio.gather(*calls, return_exceptions=True)
    errors = []
    for index, result in enumerate(raws):
        raw = {"status_code": None, "body": None, "error": f"{type(result).__name__}: {result}"} if isinstance(result, BaseException) else result
        atomic_json(args.output / "baseline" / f"case-{index:02d}.json", raw, refuse_existing=True)
        try:
            validate_raw(raw, f"baseline case {index}")
        except ValidationError as exc:
            errors.append(str(exc))
    update_state(args.output, "baseline", {"count": len(requests), "errors": errors, "elapsed_seconds": time.time() - started})
    if errors:
        raise ValidationError("; ".join(errors))


async def pinned_async(args: argparse.Namespace) -> None:
    import httpx

    fixture = load_json(args.output / "fixture.json")
    payload = load_json(args.output / fixture["request_files"][args.case_index])
    request_id = fixture["request_ids"]["pinned"][args.case_index]
    started = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        prefill, decode, endpoints = await discover_endpoints(client, args.proxy_base_url)
        prefill_payload = dict(payload)
        prefill_payload.update({"stream": False, "max_tokens": 1, "kv_transfer_params": dict(PREFILL_TRANSFER)})
        prefill_raw = await post_one(client, f"{prefill}/v1/completions", prefill_payload, {"X-Request-Id": request_id, "X-data-parallel-rank": str(args.prefill_rank)})
        atomic_json(args.output / "pinned" / f"case-{args.case_index:02d}-prefill.json", prefill_raw, refuse_existing=True)
        prefill_body = validate_raw(prefill_raw, "pinned prefill")
        transfer = prefill_body.get("kv_transfer_params")
        if not isinstance(transfer, dict) or not transfer:
            raise ValidationError("pinned prefill response lacks kv_transfer_params")
        decode_payload = dict(payload)
        decode_payload["kv_transfer_params"] = transfer
        decode_raw = await post_one(client, f"{decode}/v1/completions", decode_payload, {"X-Request-Id": request_id, "X-data-parallel-rank": str(args.decode_rank)})
        atomic_json(args.output / "pinned" / f"case-{args.case_index:02d}-decode.json", decode_raw, refuse_existing=True)
        validate_raw(decode_raw, "pinned decode")
    atomic_json(args.output / "pinned" / f"case-{args.case_index:02d}-metadata.json", {"request_id": request_id, "prefill_rank": args.prefill_rank, "decode_rank": args.decode_rank, "endpoints": endpoints}, refuse_existing=True)
    update_state(args.output, f"pinned-{args.case_index}", {"prefill_rank": args.prefill_rank, "decode_rank": args.decode_rank, "elapsed_seconds": time.time() - started})


async def proxy_async(args: argparse.Namespace) -> None:
    import httpx

    requests = requests_for(args.output)
    fixture = load_json(args.output / "fixture.json")
    limits = httpx.Limits(max_connections=len(requests), max_keepalive_connections=len(requests))
    url = f"{args.proxy_base_url.rstrip('/')}/v1/completions"
    started = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, limits=limits) as client:
        _, _, endpoints = await discover_endpoints(client, args.proxy_base_url)
        atomic_json(args.output / "proxy" / "proxy-endpoints.json", endpoints, refuse_existing=True)
        calls = [post_one(client, url, payload, {"X-Request-Id": fixture["request_ids"]["proxy"][i]}) for i, payload in enumerate(requests)]
        raws = await asyncio.gather(*calls, return_exceptions=True)
    errors = []
    for index, result in enumerate(raws):
        raw = {"status_code": None, "body": None, "error": f"{type(result).__name__}: {result}"} if isinstance(result, BaseException) else result
        atomic_json(args.output / "proxy" / f"case-{index:02d}.json", raw, refuse_existing=True)
        try:
            validate_raw(raw, f"proxy case {index}")
        except ValidationError as exc:
            errors.append(str(exc))
    update_state(args.output, "proxy-load", {"count": len(requests), "errors": errors, "elapsed_seconds": time.time() - started})
    if errors:
        raise ValidationError("; ".join(errors))


def finalize(args: argparse.Namespace) -> None:
    summary_path = args.output / "scenario-summary.json"
    errors: list[str] = []
    try:
        fixture = load_json(args.output / "fixture.json")
        state = load_json(state_path(args.output))
    except Exception as exc:
        summary = {
            "schema_version": 1,
            "scenario": args.scenario,
            "status": "failed",
            "validated": False,
            "prompt_layout": {},
            "baseline": {},
            "candidate": {},
            "exact_match_count": 0,
            "isolated_count": 0,
            "expected_key_count": None,
            "actual_key_count": None,
            "log_validation": [],
            "timing": {},
            "errors": [f"cannot load finalize state: {type(exc).__name__}: {exc}"],
        }
        atomic_json(summary_path, summary)
        raise ValidationError(summary["errors"][0]) from exc
    scenario = args.scenario
    expected_actions = {"prepare", "baseline"}
    if scenario == "s1":
        expected_actions.update(f"pinned-{index}" for index in range(4))
        expected_ranks = [0, 1, 0, 1]
        actual_ranks = [(state["actions"].get(f"pinned-{i}") or {}).get("prefill_rank") for i in range(4)]
        if actual_ranks != expected_ranks:
            expected_actions.add("pinned-ranks-0,1,0,1")
    elif scenario == "s2":
        expected_actions.add("proxy-load")
    else:
        expected_actions.update({"pinned-0", "proxy-load"})
        if (state["actions"].get("pinned-0") or {}).get("prefill_rank") != 0:
            expected_actions.add("pinned-0-rank-0")
    missing = sorted(expected_actions - set(state["actions"]))
    errors.extend(f"missing required action: {item}" for item in missing)
    actual_keys = None
    try:
        metrics = args.master_metrics.read_text(encoding="utf-8")
        actual_keys = metric_value(metrics, "master_key_count")
    except Exception as exc:
        errors.append(f"cannot load Master metrics: {type(exc).__name__}: {exc}")
    if actual_keys != fixture["expected_key_count"]:
        errors.append(f"master key count expected {fixture['expected_key_count']}, got {actual_keys}")
    log_summaries = []
    for path in args.log_check_summary:
        try:
            log_summaries.append(load_json(path))
        except Exception as exc:
            errors.append(f"cannot load log checker {path}: {type(exc).__name__}: {exc}")
    for path, summary in zip(args.log_check_summary, log_summaries):
        if summary.get("status") != "passed" or summary.get("validated") is not True:
            errors.append(f"log checker did not pass: {path}")

    candidate_dir = "pinned" if scenario == "s1" else "proxy"
    exact = isolated_count = 0
    cases = []
    for index, marker in enumerate(fixture["markers"]):
        try:
            baseline_body = validate_raw(load_json(args.output / "baseline" / f"case-{index:02d}.json"), f"baseline {index}")
            suffix = f"case-{index:02d}-decode.json" if candidate_dir == "pinned" else f"case-{index:02d}.json"
            candidate_body = validate_raw(load_json(args.output / candidate_dir / suffix), f"candidate {index}")
            baseline_signature = response_signature(baseline_body)
            candidate_signature = response_signature(candidate_body)
            exact_match = baseline_signature == candidate_signature
            prompt_count_ok = candidate_signature["prompt_tokens"] == fixture["prompt_tokens"][index]
            isolated, foreign = isolation(candidate_signature["text"], marker, fixture["markers"])
            exact += int(exact_match and prompt_count_ok)
            isolated_count += int(isolated)
            if not exact_match:
                errors.append(f"case {index}: exact response signature mismatch")
            if not prompt_count_ok:
                errors.append(f"case {index}: usage prompt_tokens mismatch")
            if not isolated:
                errors.append(f"case {index}: marker isolation failed")
            cases.append({"case": index, "exact_match": exact_match, "normalized_text_equal": normalized_text(baseline_signature["text"]) == normalized_text(candidate_signature["text"]), "prompt_tokens_match": prompt_count_ok, "isolated": isolated, "foreign_markers": foreign})
        except Exception as exc:
            errors.append(f"case {index}: {type(exc).__name__}: {exc}")
    candidate_elapsed = []
    for index in range(fixture["definition"]["case_count"]):
        suffix = f"case-{index:02d}-decode.json" if candidate_dir == "pinned" else f"case-{index:02d}.json"
        try:
            value = load_json(args.output / candidate_dir / suffix).get("elapsed_seconds")
            if isinstance(value, (int, float)):
                candidate_elapsed.append(float(value))
        except Exception:
            pass
    wall_action = "proxy-load" if candidate_dir == "proxy" else None
    wall_seconds = (state["actions"].get(wall_action) or {}).get("elapsed_seconds") if wall_action else sum(
        (state["actions"].get(f"pinned-{index}") or {}).get("elapsed_seconds", 0)
        for index in range(fixture["definition"]["case_count"])
    )
    summary = {
        "schema_version": 1,
        "scenario": scenario,
        "status": "failed" if errors else "passed",
        "validated": not errors,
        "prompt_layout": fixture,
        "baseline": {"count": fixture["definition"]["case_count"]},
        "candidate": {"source": candidate_dir, "cases": cases},
        "exact_match_count": exact,
        "isolated_count": isolated_count,
        "expected_key_count": fixture["expected_key_count"],
        "actual_key_count": actual_keys,
        "log_validation": log_summaries,
        "timing": {
            "candidate_wall_seconds": wall_seconds,
            "candidate_request_seconds_min": min(candidate_elapsed) if candidate_elapsed else None,
            "candidate_request_seconds_max": max(candidate_elapsed) if candidate_elapsed else None,
            "candidate_request_seconds_mean": (sum(candidate_elapsed) / len(candidate_elapsed)) if candidate_elapsed else None,
        },
        "errors": errors,
    }
    atomic_json(summary_path, summary)
    if errors:
        raise ValidationError("; ".join(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    common.add_argument("--output", type=Path, required=True)
    common.add_argument("--proxy-base-url", default="http://vllm-proxy-service:8000")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare", parents=[common])
    subparsers.add_parser("baseline", parents=[common])
    pinned = subparsers.add_parser("pinned-load", parents=[common])
    pinned.add_argument("--case-index", type=int, required=True)
    pinned.add_argument("--prefill-rank", type=int, choices=(0, 1), required=True)
    pinned.add_argument("--decode-rank", type=int, choices=(0,), required=True)
    subparsers.add_parser("proxy-load", parents=[common])
    final = subparsers.add_parser("finalize", parents=[common])
    final.add_argument("--master-metrics", type=Path, required=True)
    final.add_argument("--log-check-summary", type=Path, action="append", required=True)
    args = parser.parse_args()
    if not args.output.is_dir():
        parser.error(f"--output must be an existing directory: {args.output}")
    if args.command == "pinned-load" and not 0 <= args.case_index < SCENARIOS[args.scenario].case_count:
        parser.error("--case-index is outside the scenario")
    return args


def main() -> int:
    args = parse_args()
    actions = {
        "prepare": prepare,
        "baseline": lambda value: asyncio.run(baseline_async(value)),
        "pinned-load": lambda value: asyncio.run(pinned_async(value)),
        "proxy-load": lambda value: asyncio.run(proxy_async(value)),
        "finalize": finalize,
    }
    try:
        actions[args.command](args)
    except Exception as exc:
        print(f"stress-test {args.command} failed: {type(exc).__name__}: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
