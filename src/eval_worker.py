"""Evaluation worker: runs every scenario folder in its own chat session.

Layout of the data directory (default: src/evaluation/data):

    <data_dir>/<scenario>/config.yaml   application config (reports, mappings, ...), same schema as local.yaml
    <data_dir>/<scenario>/cases.jsonl   test cases: case_id, question, gold_answer, ...

Folders starting with "_" or "." are ignored (e.g. the _example folder).
For each scenario the worker opens a chat session from its config, asks every pending case in its
own conversation thread, closes the session and moves on to the next folder.
Answers go to <answers_dir>/<scenario>.jsonl (resumable, see generate.py).
"""
from __future__ import annotations

import gc
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.evaluation.conversation_asker import ConversationAsker
from src.evaluation.generate import generate_answers, load_cases, stored_case_ids

if TYPE_CHECKING:
    from src.chat_session import ChatSession

CONFIG_FILE = "config.yaml"
CASES_FILE = "cases.jsonl"
DEFAULT_DATA_DIR = Path(__file__).parent / "evaluation" / "data"

BuildSession = Callable[[Path], "ChatSession"]


@dataclass(frozen=True)
class Scenario:
    name: str
    config_path: Path
    cases_path: Path


def discover_scenarios(data_dir: Path) -> list[Scenario]:
    scenarios = []
    for folder in sorted(p for p in Path(data_dir).iterdir() if p.is_dir()):
        if folder.name.startswith(("_", ".")):
            continue
        config, cases = folder / CONFIG_FILE, folder / CASES_FILE
        missing = [p.name for p in (config, cases) if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"Scenario '{folder.name}' is missing {missing}")
        scenarios.append(Scenario(folder.name, config, cases))
    if not scenarios:
        raise FileNotFoundError(f"No scenario folders found in {data_dir}")
    return scenarios


def _isolated_config(config_path: Path, tmp: Path) -> Path:
    """Copy of the scenario config whose storage lives in `tmp`.

    Without this, every scenario would write into the same database / knowledge base, and "current
    report" (the newest stored report) would be wrong from the second scenario on.
    Assumes paths inside the config (reports, mappings) are relative to the repo root, like local.yaml.
    """
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    system = raw.setdefault("system", {})
    if system.get("store") == "knowledge_base":
        (tmp / "kb").mkdir()
        system["kb_dir"] = str(tmp / "kb")
    else:
        system["db_path"] = str(tmp / "eval.sqlite3")
    isolated = tmp / CONFIG_FILE
    isolated.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return isolated


@contextmanager
def scenario_session(config_path: Path, build_session: BuildSession) -> Iterator[ChatSession]:
    """Open a chat session on a throwaway store; closing it discards the store."""
    with tempfile.TemporaryDirectory(prefix="release_compass_eval_", ignore_cleanup_errors=True) as tmp:
        session = build_session(_isolated_config(config_path, Path(tmp)))
        try:
            yield session
        finally:
            session = None  # drop the graph/repository before the temp store is deleted
            gc.collect()


def run_eval_worker(
    *,
    data_dir: Path,
    answers_dir: Path,
    build_session: BuildSession,
    approve: bool = False,
) -> list[Path]:
    """Generate answers for every scenario. Returns the answers files that exist."""
    scenarios = discover_scenarios(data_dir)
    for scenario in scenarios:  # fail fast (TODO gold answers, duplicate ids) before any LLM call
        load_cases(scenario.cases_path)

    answers_dir = Path(answers_dir)
    answers_dir.mkdir(parents=True, exist_ok=True)
    answer_files: list[Path] = []
    failed: list[str] = []

    for scenario in scenarios:
        answers_path = answers_dir / f"{scenario.name}.jsonl"
        answer_files.append(answers_path)
        done = stored_case_ids(answers_path)
        if all(c["case_id"] in done for c in load_cases(scenario.cases_path)):
            print(f"\n=== Scenario {scenario.name}: all cases already answered, skipped ===")
            continue

        print(f"\n=== Scenario {scenario.name} ===")
        try:
            with scenario_session(scenario.config_path, build_session) as session:
                generate_answers(
                    ConversationAsker(session, approve=approve,
                                      trace_metadata={"eval_scenario": scenario.name}),
                    cases_path=scenario.cases_path,
                    answers_path=answers_path,
                )
        except Exception as error:  # one broken scenario must not stop the others
            failed.append(scenario.name)
            print(f"Scenario {scenario.name} FAILED: {error!r}")
            import traceback
            traceback.print_exc()

    if failed:
        print(f"\nFailed scenarios (rerun to retry): {failed}")
    return [p for p in answer_files if p.exists()]
