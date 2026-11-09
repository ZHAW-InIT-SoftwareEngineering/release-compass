from pathlib import Path

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field


class TraceConfig(BaseModel):
    enabled: bool = True
    auto_start: bool = True
    startup_timeout_seconds: float = Field(default=30, gt=0)
    endpoint: AnyHttpUrl = AnyHttpUrl("http://localhost:6006/v1/traces")
    project_name: str = Field(default="release-compass", min_length=1)
    service_name: str = Field(default="release-compass", min_length=1)
    export_timeout_seconds: float = Field(default=5, gt=0)


def load_trace_config(path: Path) -> TraceConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return TraceConfig.model_validate(config_data)
