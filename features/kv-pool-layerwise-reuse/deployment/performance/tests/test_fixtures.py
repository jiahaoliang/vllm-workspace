from __future__ import annotations

import json
from pathlib import Path

import pytest

from performance import fixtures
from performance.contract import WorkloadPoint


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
        return "".join(
            chr(65 + token_id) if token_id < 16 else chr(0x400 + token_id)
            for token_id in token_ids
        )

    def encode(self, text: str, **_: object) -> list[int]:
        values = [
            ord(character) - 65 if ord(character) < 128 else ord(character) - 0x400
            for character in text
        ]
        if len(values) > 1 and all(value < 16 for value in values[:2]):
            return [47, *values[2:]]
        return values


def test_exact_roundtrip_and_unique_first_block() -> None:
    tokenizer = FakeTokenizer()
    records = [
        fixtures.build_prompt(tokenizer, 4096, request_index, 20260808)
        for request_index in range(4)
    ]

    assert all(len(record.token_ids) == 4096 for record in records)
    assert all(tokenizer.encode(record.text) == list(record.token_ids) for record in records)
    assert len({record.token_ids[:128] for record in records}) == 4


def test_generator_avoids_single_token_values_that_merge_in_sequences() -> None:
    record = fixtures.build_prompt(MergingTokenizer(), 4096, 3, 20260808)

    assert len(record.token_ids) == 4096
    assert MergingTokenizer().encode(record.text) == list(record.token_ids)


def test_fixture_scans_tokenizer_alphabet_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    original = fixtures.find_roundtrip_tokens

    def counted(tokenizer: object, minimum: int = 16) -> tuple[int, ...]:
        nonlocal calls
        calls += 1
        return original(tokenizer, minimum)

    monkeypatch.setattr(fixtures, "find_roundtrip_tokens", counted)
    fixtures.write_fixture(FakeTokenizer(), 128, 4, 20260808, tmp_path)

    assert calls == 1


def test_fixture_partitions_are_disjoint_and_checksummed(tmp_path: Path) -> None:
    manifest = fixtures.write_fixture(
        FakeTokenizer(), 128, 1, 20260808, tmp_path
    )

    assert len(manifest.warmup_ids) == 8
    assert all(len(ids) == 32 for ids in manifest.formal_ids)
    partitions = (set(manifest.warmup_ids), *(set(ids) for ids in manifest.formal_ids))
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(partitions)
        for right in partitions[index + 1 :]
    )
    row = json.loads(manifest.partition_files["warmup"].read_text().splitlines()[0])
    assert set(row) == {"question", "answer", "request_id"}
    assert row["answer"] == ""
    assert fixtures.replay_fixture(manifest) == []


def test_aisbench_config_preserves_point_and_prompt(tmp_path: Path) -> None:
    dataset = tmp_path / "formal-1.jsonl"
    dataset.write_text('{"question":"x","answer":"","request_id":"r"}\n')
    point = WorkloadPoint("dp1", 4096, 128, "bulk", 4)
    output = tmp_path / "point.py"

    fixtures.write_aisbench_config(point, dataset, output, request_count=32)

    text = output.read_text(encoding="utf-8")
    compile(text, str(output), "exec")
    assert "stream=True" in text
    assert "retry=0" in text
    assert "batch_size=4" in text
    assert "request_rate=0" in text
    assert "max_out_len=128" in text
    assert "temperature=0" in text
    assert "ignore_eos=True" in text
    assert 'template="{question}"' in text
    meta = json.loads(
        dataset.with_name(dataset.name + ".meta.json").read_text(encoding="utf-8")
    )
    assert meta == {"request_count": 32, "sampling_mode": "default"}
    assert "request_count=32" not in text
    assert (
        "from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate"
        in text
    )
    assert (
        "from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever" in text
    )
    assert (
        "from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer" in text
    )
    assert "type=NaivePartitioner" in text
    assert "type=LocalAPIRunner" in text
    assert "type=OpenICLInferTask" in text


def test_fixture_corruption_breaks_checksum_replay(tmp_path: Path) -> None:
    manifest = fixtures.write_fixture(FakeTokenizer(), 128, 1, 20260808, tmp_path)
    manifest.partition_files["formal-2"].write_text("changed\n", encoding="utf-8")

    assert fixtures.replay_fixture(manifest) == [
        "fixture checksum mismatch: formal-2.jsonl"
    ]


def test_config_cli_writes_attempt_local_metadata(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"question":"x","answer":""}\n', encoding="utf-8")

    result = fixtures.main(
        [
            "config",
            "--topology",
            "dp2",
            "--input-tokens",
            "16384",
            "--output-tokens",
            "1",
            "--variant",
            "reuse3",
            "--concurrency",
            "32",
            "--dataset",
            str(dataset),
            "--request-count",
            "256",
            "--output",
            str(tmp_path / "config.py"),
        ]
    )

    assert result == 0
    assert json.loads((tmp_path / "dataset.jsonl.meta.json").read_text())[
        "request_count"
    ] == 256
    assert "batch_size=32" in (tmp_path / "config.py").read_text()
