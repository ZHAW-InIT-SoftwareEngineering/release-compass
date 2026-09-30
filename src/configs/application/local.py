from pathlib import Path

import yaml
from pydantic import BaseModel


class LocalConfig(BaseModel):
    db_path: Path


def load_local_config(path: Path) -> LocalConfig:
    with path.open(encoding="utf-8") as config_file:
        config_data = yaml.safe_load(config_file)
    return LocalConfig.model_validate(config_data)
