from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from performance import fixtures
from performance.contract import SEED_TOKENS, WorkloadPoint


class FakeTokenizer:
    vocab_size = 80
    all_special_ids = [0, 1]
    name_or_path = "fake-tokenizer"

    def decode(self, token_ids: list[int], **_: object) -> str:
        return "".join(chr(0x400 + token_id) for token_id in token_ids)

    def encode(self, text: str, **_: object) -> list[int]:
        return [ord(character) - 0x400 for character in text]


class MergingTokenizer:
    vocab_size = 48
    all_special_ids: list[int] = []
    name_or_path = "merging-tokenizer"

    def decode(self, token_ids: list[int], **_: object) -> str:
        return "".join(chr(65 + token_id) if token_id < 16 else chr(0x400 + token_id) for token_id in token_ids)

    def encode(self, text: str, **_: object) -> list[int]:
        values = [ord(character) - 65 if ord(character) < 128 else ord(character) - 0x400 for character in text]
        if len(values) > 1 and all(value < 16 for value in values[:2]):
            return [47, *values[2:]]
        return values


def _formal_fixture(tmp_path: Path, input_tokens: int = 256) -> tuple[Path, Path]:
    input_tokens = max(input_tokens, 256)
    generated = fixtures.write_fixture(
        FakeTokenizer(), input_tokens, 8, 20260808, tmp_path, seed_tokens=128
    )
    return generated.partition_files["formal-1"], generated.manifest_file


def test_exact_roundtrip_and_unique_first_block() -> None:
    tokenizer = FakeTokenizer()
    records = [fixtures.build_prompt(tokenizer, 4096, request_index, 20260808) for request_index in range(4)]

    assert all(len(record.token_ids) == 4096 for record in records)
    assert all(tokenizer.encode(record.text) == list(record.token_ids) for record in records)
    assert len({record.token_ids[:128] for record in records}) == 4


def test_generator_avoids_single_token_values_that_merge_in_sequences() -> None:
    record = fixtures.build_prompt(MergingTokenizer(), 4096, 3, 20260808)

    assert len(record.token_ids) == 4096
    assert MergingTokenizer().encode(record.text) == list(record.token_ids)


def test_fixture_scans_tokenizer_alphabet_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    original = fixtures.find_roundtrip_tokens

    def counted(tokenizer: object, minimum: int = 16) -> tuple[int, ...]:
        nonlocal calls
        calls += 1
        return original(tokenizer, minimum)

    monkeypatch.setattr(fixtures, "find_roundtrip_tokens", counted)
    fixtures.write_fixture(FakeTokenizer(), 256, 8, 20260808, tmp_path, seed_tokens=128)

    assert calls == 1


def test_fixture_partitions_are_disjoint_and_checksummed(tmp_path: Path) -> None:
    manifest = fixtures.write_fixture(FakeTokenizer(), 256, 8, 20260808, tmp_path, seed_tokens=128)

    assert len(manifest.warmup_ids) == 8
    assert len(manifest.seed_ids) == 64
    assert len(manifest.formal_ids) == 1
    assert all(len(ids) == 64 for ids in manifest.formal_ids)
    partitions = (
        set(manifest.warmup_ids),
        set(manifest.seed_ids),
        *(set(ids) for ids in manifest.formal_ids),
    )
    assert all(left.isdisjoint(right) for index, left in enumerate(partitions) for right in partitions[index + 1 :])
    row = json.loads(manifest.partition_files["warmup"].read_text().splitlines()[0])
    assert set(row) == {"question", "answer", "request_id"}
    assert row["answer"] == ""
    assert fixtures.replay_fixture(manifest) == []


def test_seed_rows_are_exact_formal_prefixes(tmp_path: Path) -> None:
    input_tokens = SEED_TOKENS + 128
    manifest = fixtures.write_fixture(
        FakeTokenizer(), input_tokens, 8, 20260808, tmp_path
    )

    seed_rows = [
        json.loads(line)
        for line in manifest.partition_files["seed"].read_text(encoding="utf-8").splitlines()
    ]
    formal_rows = [
        json.loads(line)
        for line in manifest.partition_files["formal-1"].read_text(encoding="utf-8").splitlines()
    ]
    fixture_manifest = json.loads(manifest.manifest_file.read_text(encoding="utf-8"))

    assert len(seed_rows) == len(formal_rows) == 64
    assert fixture_manifest["seed_tokens"] == SEED_TOKENS
    assert fixture_manifest["formal_tokens"] == input_tokens
    assert fixture_manifest["expected_hit_rate"] == SEED_TOKENS / input_tokens
    assert len(fixture_manifest["seed_formal_pairs"]) == 64
    for seed, formal, pair in zip(
        seed_rows,
        formal_rows,
        fixture_manifest["seed_formal_pairs"],
    ):
        seed_tokens = FakeTokenizer().encode(seed["question"])
        formal_tokens = FakeTokenizer().encode(formal["question"])
        assert len(seed_tokens) == SEED_TOKENS
        assert len(formal_tokens) == input_tokens
        assert seed_tokens == formal_tokens[:SEED_TOKENS]
        assert pair["seed_request_id"] == seed["request_id"]
        assert pair["formal_request_id"] == formal["request_id"]
        seed_digest = hashlib.sha256(
            json.dumps(seed_tokens, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        formal_digest = hashlib.sha256(
            json.dumps(formal_tokens, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        assert pair["seed_token_ids_sha256"] == seed_digest
        assert pair["formal_prefix_token_ids_sha256"] == seed_digest
        assert pair["formal_token_ids_sha256"] == formal_digest


def test_seed_attempt_contract_uses_seed_length(tmp_path: Path) -> None:
    manifest = fixtures.write_fixture(
        FakeTokenizer(), SEED_TOKENS + 128, 8, 20260808, tmp_path
    )
    point = WorkloadPoint("dp1", SEED_TOKENS + 128, 1, "bulk", 8)

    attempt = fixtures.build_attempt_contract(
        point,
        "seed",
        manifest.partition_files["seed"],
        manifest.manifest_file,
        64,
    )

    assert attempt["phase"] == "seed"
    assert attempt["input_tokens"] == SEED_TOKENS
    assert attempt["formal_input_tokens"] == SEED_TOKENS + 128
    assert attempt["request_count"] == 64


def test_aisbench_config_preserves_point_and_prompt(tmp_path: Path) -> None:
    dataset, manifest = _formal_fixture(tmp_path)
    point = WorkloadPoint("dp1", 256, 128, "bulk", 8)
    output = tmp_path / "point.py"

    fixtures.write_aisbench_config(point, dataset, output, request_count=64,
        phase="formal-1",
        fixture_manifest=manifest,
    )

    text = output.read_text(encoding="utf-8")
    compile(text, str(output), "exec")
    assert "stream=True" in text
    assert "retry=1" in text
    assert "one total request attempt" in text
    assert "pressure" not in text
    assert "batch_size=8" in text
    assert "request_rate=0" in text
    assert "max_out_len=128" in text
    assert text.count("abbr='bulk'") == 2
    assert 'attr="performance"' in text
    assert "type=DefaultPerfSummarizer" in text
    assert "type=DefaultPerfMetricCalculator" in text
    assert "StablePerfMetricCalculator" not in text
    assert "temperature=0" in text
    assert "ignore_eos=True" in text
    assert 'template="{question}"' in text
    meta = json.loads(dataset.with_name(dataset.name + ".meta.json").read_text(encoding="utf-8"))
    assert meta == {"request_count": 64, "sampling_mode": "default"}
    assert "request_count=64" not in text
    assert (
        "from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate" in text
    )
    assert "from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever" in text
    assert (
        "from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer" in text
    )
    assert "type=NaivePartitioner" in text
    assert "from ais_bench.benchmark.runners import LocalRunner" in text
    assert "from ais_bench.benchmark.tasks import OpenICLApiInferTask" in text
    assert "type=LocalRunner" in text
    assert "type=OpenICLApiInferTask" in text
    attempt_contract = json.loads(
        (output.parent / "attempt-contract.json").read_text(encoding="utf-8")
    )
    assert attempt_contract == {
        "schema_version": 1,
        "phase": "formal-1",
        "point_id": "dp1-256-bulk-o128-c8",
        "topology": "dp1",
        "variant": "bulk",
        "input_tokens": 256,
        "formal_input_tokens": 256,
        "output_tokens": 128,
        "concurrency": 8,
        "request_count": 64,
        "dataset_line_count": 64,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "fixture_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }


def test_attempt_contract_rejects_wrong_line_count_before_config(
    tmp_path: Path,
) -> None:
    dataset, manifest = _formal_fixture(tmp_path)
    dataset.write_text(
        dataset.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="dataset line count mismatch"):
        fixtures.write_aisbench_config(
            WorkloadPoint("dp1", 256, 1, "bulk", 8),
            dataset,
            tmp_path / "config.py",
            request_count=64,
            phase="formal-1",
            fixture_manifest=manifest,
        )

    assert not (tmp_path / "config.py").exists()


def test_attempt_contract_rejects_malformed_json_before_config(tmp_path: Path) -> None:
    dataset, manifest = _formal_fixture(tmp_path)
    lines = dataset.read_text(encoding="utf-8").splitlines()
    lines[0] = "not-json"
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dataset row 1 is not valid JSON"):
        fixtures.write_aisbench_config(
            WorkloadPoint("dp1", 256, 1, "bulk", 8),
            dataset,
            tmp_path / "config.py",
            request_count=64,
            phase="formal-1",
            fixture_manifest=manifest,
        )


def test_attempt_contract_rejects_wrong_prompt_shape_before_config(
    tmp_path: Path,
) -> None:
    dataset, manifest = _formal_fixture(tmp_path)
    lines = dataset.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    del row["question"]
    lines[0] = json.dumps(row)
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(TypeError, match="dataset row 1 lacks a string question"):
        fixtures.write_aisbench_config(
            WorkloadPoint("dp1", 256, 1, "bulk", 8),
            dataset,
            tmp_path / "config.py",
            request_count=64,
            phase="formal-1",
            fixture_manifest=manifest,
        )


def test_attempt_contract_rejects_manifest_token_length_mismatch(
    tmp_path: Path,
) -> None:
    dataset, manifest = _formal_fixture(tmp_path)

    with pytest.raises(ValueError, match="fixture input token mismatch"):
        fixtures.write_aisbench_config(
            WorkloadPoint("dp1", 16384, 1, "bulk", 8),
            dataset,
            tmp_path / "config.py",
            request_count=64,
            phase="formal-1",
            fixture_manifest=manifest,
        )


def test_attempt_contract_rejects_dataset_checksum_mismatch(tmp_path: Path) -> None:
    dataset, manifest = _formal_fixture(tmp_path)
    lines = dataset.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["answer"] = "changed"
    lines[0] = json.dumps(row)
    dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dataset checksum mismatch"):
        fixtures.write_aisbench_config(
            WorkloadPoint("dp1", 256, 1, "bulk", 8),
            dataset,
            tmp_path / "config.py",
            request_count=64,
            phase="formal-1",
            fixture_manifest=manifest,
        )


def test_fixture_corruption_breaks_checksum_replay(tmp_path: Path) -> None:
    manifest = fixtures.write_fixture(FakeTokenizer(), 256, 8, 20260808, tmp_path, seed_tokens=128)
    manifest.partition_files["formal-1"].write_text("changed\n", encoding="utf-8")

    assert fixtures.replay_fixture(manifest) == ["fixture checksum mismatch: formal-1.jsonl"]


def test_config_cli_writes_attempt_local_metadata(tmp_path: Path) -> None:
    dataset, manifest = _formal_fixture(tmp_path)

    result = fixtures.main(
        [
            "config",
            "--topology",
            "dp1",
            "--input-tokens",
            "256",
            "--output-tokens",
            "1",
            "--variant",
            "reuse3",
            "--concurrency",
            "8",
            "--dataset",
            str(dataset),
            "--request-count",
            "64",
            "--phase",
            "formal-1",
            "--fixture-manifest",
            str(manifest),
            "--output",
            str(tmp_path / "config.py"),
        ]
    )

    assert result == 0
    assert (
        json.loads(dataset.with_name(dataset.name + ".meta.json").read_text())["request_count"] == 64
    )
    assert "batch_size=8" in (tmp_path / "config.py").read_text()
    assert (
        json.loads((tmp_path / "attempt-contract.json").read_text())["phase"]
        == "formal-1"
    )
