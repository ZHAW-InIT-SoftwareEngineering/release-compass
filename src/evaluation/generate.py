"""Stage 1: ask each case's question and store the answer. Resumable.

Appends one JSON line per case to the answers file:
    {"timestamp", "case_id", "question", "answer", "gold_answer", "requirement_id", "latency_ms"}
A case_id that is already in the file is skipped; a case whose call fails is NOT written,
so it is retried on the next run. One answers file = one chatbot version: use a new file
to evaluate a new release (otherwise every case would be skipped).
"""
import json
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Ask = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case_id in cases file")
    todo = [c["case_id"] for c in cases if c["gold_answer"].lstrip().upper().startswith("TODO")]
    if todo:
        raise ValueError(f"Gold answers still marked TODO: {todo}")
    return cases


def stored_case_ids(answers_path: Path) -> set[str]:
    ids: set[str] = set()
    if not answers_path.exists():
        return ids
    for number, line in enumerate(answers_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            ids.add(json.loads(line)["case_id"])
        except (json.JSONDecodeError, KeyError):
            print(f"WARNING {answers_path}:{number} is not a valid record, ignored")
    return ids


def _ensure_trailing_newline(path: Path) -> None:
    """Guard against a half-written last line (e.g. crash) gluing onto the next record."""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as f:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                with path.open("ab") as g:
                    g.write(b"\n")


def generate_answers(ask: Ask, *, cases_path: Path, answers_path: Path) -> tuple[int, int, int]:
    """Returns (written, skipped, failed)."""
    cases = load_cases(cases_path)
    answers_path = Path(answers_path)
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_trailing_newline(answers_path)
    done = stored_case_ids(answers_path)

    written = skipped = failed = 0
    for case in cases:
        case_id = case["case_id"]
        if case_id in done:
            skipped += 1
            print(f"{case_id}  skipped (already in {answers_path.name})")
            continue
        try:
            started = time.perf_counter()
            reply = ask(case["question"], case)
            latency_ms = (time.perf_counter() - started) * 1000
            answer = reply["answer"]
            if not answer:
                raise ValueError("empty answer")
        except Exception as error:  # not written -> retried next run
            failed += 1
            print(f"{case_id}  FAILED: {error!r}")
            continue

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "case_id": case_id,
            "question": case["question"],
            "answer": answer,
            "gold_answer": case["gold_answer"],
            "requirement_id": case.get("requirement_id"),
            "latency_ms": round(latency_ms, 1),
        }
        with answers_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        written += 1
        print(f"{case_id}  answered in {latency_ms:.0f} ms")

    print(f"\nGeneration done: {written} written, {skipped} skipped, {failed} failed -> {answers_path}")
    return written, skipped, failed
