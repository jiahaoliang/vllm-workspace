"""Run one candidate LAYERWISE point against the immutable formal control."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from performance import runner
from performance.contract import (
    FORMAL_REQUEST_COUNT,
    TOPOLOGIES,
    WARMUP_REQUEST_COUNT,
    WorkloadPoint,
    point_id,
)


POINT = WorkloadPoint("dp1", 16384, 1, "layerwise", 8)
PATCH_TARGET = (
    "/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/"
    "kv_pool/ascend_store/pool_worker.py"
)
CONTROL_FILES = (
    "raw/run-contract.json",
    "raw/image/image-resolution.json",
    "raw/canaries/dp1-16384-layerwise.json",
    "raw/points/dp1-16384-layerwise-o1-c8/warmup/attempt-1/raw/mooncake.metrics",
    "raw/points/dp1-16384-layerwise-o1-c8/formal-1/attempt-1/raw/mooncake.metrics",
    "raw/points/dp1-16384-layerwise-o1-c8/formal-1/attempt-1/raw/summary.json",
    "raw/variants/layerwise/raw/vllm-prefill.log",
    "raw/restoration.json",
)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate_control(control: Path, output: Path) -> None:
    manifest_path = control / "SHA256SUMS"
    manifest = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name:
            raise ValueError(f"malformed control checksum row: {line}")
        manifest[name] = digest

    verified = {}
    for name in CONTROL_FILES:
        path = control / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest.get(name) != actual:
            raise ValueError(f"control checksum mismatch: {name}")
        verified[name] = actual

    contract = _load_json(control / "raw/run-contract.json")
    selected_point = point_id(POINT)
    if selected_point not in contract.get("expected_points", []):
        raise ValueError(f"control does not contain {selected_point}")
    if contract.get("warmup_request_count") != WARMUP_REQUEST_COUNT:
        raise ValueError("control warmup request count mismatch")
    if contract.get("formal_request_count") != FORMAL_REQUEST_COUNT:
        raise ValueError("control formal request count mismatch")

    summary = _load_json(
        control
        / "raw/points/dp1-16384-layerwise-o1-c8/formal-1/attempt-1/raw/summary.json"
    )
    if (
        summary.get("valid") is not True
        or summary.get("success_count") != FORMAL_REQUEST_COUNT
    ):
        raise ValueError("control point is not a valid 64/64 result")
    restoration = _load_json(control / "raw/restoration.json")
    if restoration.get("completed") is not True:
        raise ValueError("control run did not restore successfully")

    runner._write_json(
        output / "control-provenance.json",
        {
            "root": str(control.resolve()),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "point": selected_point,
            "selected_files": verified,
        },
    )


def _verify_candidate(
    command_runner: runner.Runner,
    output: Path,
    reference: str,
    digest: str,
    patch_sha256: str,
) -> str:
    inspected_raw = command_runner.run(
        runner.Command(
            ("nerdctl", "--namespace", "k8s.io", "image", "inspect", reference),
            description="inspect-candidate-image",
        )
    )
    inspected_list = json.loads(inspected_raw)
    if not isinstance(inspected_list, list) or len(inspected_list) != 1:
        raise ValueError("candidate image inspect did not return one image")
    inspected = inspected_list[0]
    if not isinstance(inspected, dict):
        raise ValueError("candidate image inspect result is malformed")
    if (inspected.get("Os"), inspected.get("Architecture")) != ("linux", "arm64"):
        raise ValueError("candidate image is not linux/arm64")
    repo_digests = inspected.get("RepoDigests", [])
    if not isinstance(repo_digests, list) or not any(
        str(value).endswith(f"@{digest}") for value in repo_digests
    ):
        raise ValueError("candidate manifest digest mismatch")

    actual_patch = command_runner.run(
        runner.Command(
            (
                "nerdctl",
                "--namespace",
                "k8s.io",
                "run",
                "--rm",
                "--net",
                "none",
                "--entrypoint",
                "sha256sum",
                reference,
                PATCH_TARGET,
            ),
            description="verify-candidate-patch",
        )
    ).split()[0]
    if actual_patch != patch_sha256:
        raise ValueError("candidate pool_worker.py SHA256 mismatch")

    config = inspected.get("Config", {})
    labels = config.get("Labels", {}) if isinstance(config, dict) else {}
    runner._write_json(
        output / "candidate-image.json",
        {
            "reference": reference,
            "manifest_digest": digest,
            "config_digest": inspected.get("Id"),
            "platform": "linux/arm64",
            "patch_target": PATCH_TARGET,
            "patch_sha256": actual_patch,
            "comment": inspected.get("Comment"),
            "source_labels": labels,
        },
    )
    config_digest = inspected.get("Id")
    if not isinstance(config_digest, str) or not config_digest.startswith("sha256:"):
        raise ValueError("candidate config digest is unavailable")
    return config_digest


def _assert_deployed_image(
    command_runner: runner.Runner,
    output: Path,
    reference: str,
    config_digest: str,
) -> None:
    raw = runner._run_and_save(
        command_runner,
        runner.Command(
            (
                "kubectl",
                "get",
                "pods",
                "-n",
                "liangjiahao",
                "-l",
                "app in (prefill,decode)",
                "-o",
                "json",
            ),
            description="verify-deployed-candidate-image",
        ),
        output / "deployed-image-pods.json",
    )
    value = json.loads(raw)
    items = value.get("items", []) if isinstance(value, dict) else []
    if not isinstance(items, list) or len(items) != 2:
        raise ValueError("expected exactly two deployed engine Pods")
    observed = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("deployed engine Pod is malformed")
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}
        role = labels.get("app") if isinstance(labels, dict) else None
        if role not in {"prefill", "decode"} or role in observed:
            raise ValueError(f"unexpected deployed engine role: {role}")
        containers = spec.get("containers", []) if isinstance(spec, dict) else []
        statuses = status.get("containerStatuses", []) if isinstance(status, dict) else []
        if not isinstance(containers, list) or len(containers) != 1:
            raise ValueError(f"unexpected deployed container count: {role}")
        if not isinstance(statuses, list) or len(statuses) != 1:
            raise ValueError(f"unexpected deployed status count: {role}")
        image_reference = containers[0].get("image")
        image_id = statuses[0].get("imageID")
        if image_reference != reference or image_id != config_digest:
            raise ValueError(
                f"deployed candidate image mismatch: {role}: "
                f"reference={image_reference} imageID={image_id}"
            )
        observed[role] = {"reference": image_reference, "image_id": image_id}
    runner._write_json(output / "deployed-image.json", observed)


def _capture_source_identity(
    command_runner: runner.Runner,
    output: Path,
    source_commit: str,
) -> str:
    values: dict[str, object] = {}
    source_status: list[str] | None = None
    for name, repository in (
        ("control repo", runner.WORKSPACE_ROOT),
        ("repos/vllm", runner.WORKSPACE_ROOT / "repos/vllm"),
        ("repos/vllm-ascend", runner.WORKSPACE_ROOT / "repos/vllm-ascend"),
        ("repos/Mooncake", runner.WORKSPACE_ROOT / "repos/Mooncake"),
    ):
        head = command_runner.run(
            runner.Command(
                ("git", "-C", str(repository), "rev-parse", "HEAD"),
                description=f"source-{name.replace('/', '-')}",
            )
        ).strip()
        status = command_runner.run(
            runner.Command(
                ("git", "-C", str(repository), "status", "--porcelain"),
                description=f"dirty-{name.replace('/', '-')}",
            )
        ).splitlines()
        values[name] = {"commit": head, "dirty": status}
        if name == "repos/vllm-ascend":
            source_status = status

    source_repo = runner.WORKSPACE_ROOT / "repos/vllm-ascend"
    if source_status is None:
        raise AssertionError("repos/vllm-ascend identity was not captured")
    if source_status:
        raise ValueError("repos/vllm-ascend checkout must be clean")
    resolved_commit = command_runner.run(
        runner.Command(
            (
                "git",
                "-C",
                str(source_repo),
                "rev-parse",
                "--verify",
                f"{source_commit}^{{commit}}",
            ),
            description="source-commit",
        )
    ).strip()
    source_tree = command_runner.run(
        runner.Command(
            (
                "git",
                "-C",
                str(source_repo),
                "rev-parse",
                f"{resolved_commit}^{{tree}}",
            ),
            description="source-commit-tree",
        )
    ).strip()
    head_tree = command_runner.run(
        runner.Command(
            ("git", "-C", str(source_repo), "rev-parse", "HEAD^{tree}"),
            description="source-head-tree",
        )
    ).strip()
    if source_tree != head_tree:
        raise ValueError("candidate checkout HEAD tree differs from source commit tree")
    production_diff = command_runner.run(
        runner.Command(
            (
                "git",
                "-C",
                str(source_repo),
                "diff",
                f"{resolved_commit}^",
                resolved_commit,
                "--",
                "vllm_ascend/distributed/kv_transfer/kv_pool/ascend_store/pool_worker.py",
            ),
            description="candidate-production-diff",
        )
    )
    (output / "candidate-production.patch").write_text(production_diff, encoding="utf-8")
    values["source_commit"] = resolved_commit
    values["source_commit_tree"] = source_tree
    values["head_tree"] = head_tree
    values["candidate_production_patch_sha256"] = hashlib.sha256(
        production_diff.encode("utf-8")
    ).hexdigest()
    runner._write_json(output / "source-identity.json", values)

    client = runner._run_and_save(
        command_runner,
        runner.Command(
            (
                "kubectl",
                "get",
                "pod",
                "-n",
                "liangjiahao",
                "layerwise-performance-aisbench",
                "-o",
                "json",
            ),
            description="capture-client-identity",
        ),
        output / "client-identity.json",
    )
    if not isinstance(json.loads(client), dict):
        raise ValueError("client identity is not a JSON object")
    return resolved_commit


def run_ab(args: argparse.Namespace) -> None:
    output: Path = args.output
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"A/B output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    _validate_control(args.control, output)
    command_runner = runner.SubprocessCommandRunner(output)
    candidate_config_digest = _verify_candidate(
        command_runner,
        output,
        args.image,
        args.image_digest,
        args.patch_sha256,
    )
    runner._sync_client_tooling(command_runner, output)
    runner._archive_shared_fixtures(command_runner, output)
    source_commit = _capture_source_identity(
        command_runner, output, args.source_commit
    )
    inputs = runner._capture_pre_run_state(command_runner, output)

    nodes = _load_json(output / "cluster/nodes.json")
    pods = _load_json(output / "cluster/pods.json")
    available_npus = runner._available_test_npus(nodes, pods, args.npu_node)
    topology = TOPOLOGIES[POINT.topology]
    required_npus = topology.prefill_npus + topology.decode_npus
    runner._write_json(
        output / "cluster/dp1-capacity.json",
        {
            "node": args.npu_node,
            "resource": "huawei.com/Ascend910",
            "available_after_replacing_current_engines": available_npus,
            "required": required_npus,
            "vnpu_number_ignored": True,
        },
    )
    if available_npus < required_npus:
        raise RuntimeError(
            "insufficient physical Ascend910 capacity: "
            f"{available_npus} < {required_npus}"
        )

    selected_point = point_id(POINT)
    contract = {
        "kind": "single-variable-causal-ab",
        "hypothesis": (
            "no-reuse layerwise requests with load_spec=None unnecessarily "
            "inherit self-saved keys"
        ),
        "control_root": str(args.control.resolve()),
        "candidate_image": args.image,
        "candidate_image_digest": args.image_digest,
        "candidate_patch_sha256": args.patch_sha256,
        "source_commit": source_commit,
        "npu_node": args.npu_node,
        "expected_points": [selected_point],
        "warmup_request_count": WARMUP_REQUEST_COUNT,
        "formal_request_count": FORMAL_REQUEST_COUNT,
        "formal_repetitions": 1,
        "formal_concurrency_waves": FORMAL_REQUEST_COUNT // POINT.concurrency,
        "only_changed_runtime_variable": (
            "pool_worker no-reuse/no-load_spec tracker inheritance"
        ),
        "raw_characterization_only": True,
    }
    runner._write_json(output / "run-contract.json", contract)
    environment = runner.RunEnvironment(
        restore_manifest=output / "pre-run-state",
        image_digest=args.image_digest,
    )
    rendered, paths = runner._write_rendered_block(inputs, POINT, args.image, output)
    configmaps = {str(rendered.runtime_configmap["metadata"]["name"])}
    run_error: BaseException | None = None
    try:
        runner._apply_variant_block(command_runner, paths, POINT, environment, output)
        _assert_deployed_image(
            command_runner,
            output,
            args.image,
            candidate_config_digest,
        )
        runner._run_variant_canary(command_runner, POINT, environment, output)
        point_root = output / "points" / selected_point
        runner._write_json(
            point_root / "identity.json",
            {
                "image_digest": args.image_digest,
                "variant": POINT.variant,
                "topology": POINT.topology,
                "input_tokens": POINT.input_tokens,
                "output_tokens": POINT.output_tokens,
                "concurrency": POINT.concurrency,
            },
        )
        summaries = runner.execute_point(command_runner, POINT, output, environment)
        runner._write_json(output / "candidate-formal-summary.json", summaries[0])
        runner._capture_variant_diagnostics(command_runner, POINT.variant, environment, output)
        stop_errors = runner._stop_engines(command_runner, environment)
        if stop_errors:
            raise RuntimeError("; ".join(stop_errors))
    except BaseException as error:
        run_error = error

    restoration_errors = runner._restore_pre_run_state(
        command_runner,
        output,
        environment,
        configmaps,
    )
    runner._write_json(
        output / "ab-state.json",
        {
            "run_completed": run_error is None,
            "run_error": None
            if run_error is None
            else {"type": type(run_error).__name__, "message": str(run_error)},
            "restoration_errors": restoration_errors,
        },
    )
    runner._write_checksums(output)
    if run_error is not None:
        raise run_error
    if restoration_errors:
        raise RuntimeError("restoration failed: " + "; ".join(restoration_errors))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--patch-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--npu-node", default="n1")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_ab(_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
