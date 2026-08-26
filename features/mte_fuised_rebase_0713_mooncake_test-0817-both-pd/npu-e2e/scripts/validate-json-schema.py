#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def load_instances(path: Path, jsonl: bool) -> list[object]:
    if not jsonl:
        return [json.loads(path.read_text(encoding="utf-8"))]
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema", type=Path)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failed = False
    for index, instance in enumerate(load_instances(args.instance, args.jsonl), 1):
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            prefix = f"record {index}: " if args.jsonl else ""
            print(f"{prefix}{location}: {error.message}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
