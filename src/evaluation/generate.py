"""Stage 1: ask each case's question and store the answer. Resumable.

All answers of all scenarios go into ONE json file with this structure:

    {
      "summary": null | {...},      # written by score.py; reset to null whenever a new case is added
      "cases": [
        {"timestamp", "scenario", "case_id", "question", "answer", "gold_answer",
         "tags", "requirement_id", "latency_ms", "scoring"?}   # "scoring" is added by score.py
      ]
    }

A (scenario, case_id) pair that is already in the file is skipped; a case whose call fails is NOT
written, so it is retried on the next run. One answers file = one chatbot version: use a new file
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


def load_answers(path: Path) -> dict[str, Any]:
    """Read the answers file; a missing or empty file gives an empty structure."""
    path = Path(path)
    if not path.exists():
        return {"summary": None, "cases": []}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {"summary": None, "cases": []}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{path} is not a valid answers file (an old .jsonl file? delete it or use a new --output): {error}"
        ) from error
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"{path} has an unexpected structure: expected an object with a 'cases' list")
    data.setdefault("summary", None)
    return data


def save_answers(path: Path, data: Mapping[str, Any]) -> None:
    """Write atomically, so a crash cannot leave a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def stored_case_ids(answers_path: Path, scenario: str | None = None) -> set[str]:
    """case_ids already answered (for one scenario, or for all if scenario is None)."""
    return {
        c["case_id"]
        for c in load_answers(answers_path)["cases"]
        if scenario is None or c.get("scenario") == scenario
    }


def generate_answers(
    ask: Ask,
    *,
    cases_path: Path,
    answers_path: Path,
    scenario: str | None = None,
) -> tuple[int, int, int]:
    """Returns (written, skipped, failed)."""
    cases = load_cases(cases_path)
    answers_path = Path(answers_path)
    data = load_answers(answers_path)
    done = {
        c["case_id"] for c in data["cases"]
        if scenario is None or c.get("scenario") == scenario
    }

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
            "scenario": scenario,
            "case_id": case_id,
            "question": case["question"],
            "answer": answer,
            "gold_answer": case["gold_answer"],
            "tags": case.get("tags", []),
            "requirement_id": case.get("requirement_id"),
            "latency_ms": round(latency_ms, 1),
        }
        data["cases"].append(record)
        data["summary"] = None  # a new case makes the aggregate outdated until it is re-scored
        save_answers(answers_path, data)
        written += 1
        print(f"{case_id}  answered in {latency_ms:.0f} ms")

    print(f"\nGeneration done: {written} written, {skipped} skipped, {failed} failed -> {answers_path}")
    return written, skipped, failed