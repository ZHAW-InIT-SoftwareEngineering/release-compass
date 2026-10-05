from pathlib import Path

import yaml
from pydantic import BaseModel


class SystemConfig(BaseModel):
    db_path: Path


class ReportInputConfig(BaseModel):
    path: Path
    generated_at_date: str
    generated_at_time: str


class DataConfig(BaseModel):
    reports: list[ReportInputConfig]


class LocalConfig(BaseModel):
    system: SystemConfig
    data: DataConfig


def load_local_config(path: Path) -> LocalConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return LocalConfig.model_validate(config_data)
