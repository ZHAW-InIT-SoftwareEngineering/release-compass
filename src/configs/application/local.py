from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator


class SystemConfig(BaseModel):
    # Adapter of ReportRepository used by the composition root (ADR 0013).
    store: Literal["knowledge_base", "sqlite"] = "knowledge_base"
    # Folder of the knowledge base Turtle files, e.g. facts.ttl.
    kb_dir: Path | None = None
    db_path: Path | None = None
    # LLM endpoint config: OpenRouter by default, SGLang when self-hosted (ADR 0016).
    llm: Path = Path("configs/llm/openrouter.yaml")

    @model_validator(mode="after")
    def _check_store_path(self):
        path = self.kb_dir if self.store == "knowledge_base" else self.db_path
        if path is None:
            name = "kb_dir" if self.store == "knowledge_base" else "db_path"
            raise ValueError(f"Store {self.store!r} requires system.{name}")
        return self


class IngestionConfig(BaseModel):
    # Source name -> HTML mapping configuration file.
    mappings: dict[str, Path]


class ReportInputConfig(BaseModel):
    path: Path
    source: str
    generated_at_date: str | None = None
    generated_at_time: str | None = None


class DataConfig(BaseModel):
    reports: list[ReportInputConfig]


class LocalConfig(BaseModel):
    system: SystemConfig
    ingestion: IngestionConfig
    data: DataConfig

    @model_validator(mode="after")
    def _check_report_sources(self):
        for report in self.data.reports:
            if report.source not in self.ingestion.mappings:
                raise ValueError(
                    f"Report {report.path} uses source {report.source!r} "
                    "without an ingestion mapping"
                )
        return self


def load_local_config(path: Path) -> LocalConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return LocalConfig.model_validate(config_data)
