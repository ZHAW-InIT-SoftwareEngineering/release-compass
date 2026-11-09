from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator


class SystemConfig(BaseModel):
    db_path: Path


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
