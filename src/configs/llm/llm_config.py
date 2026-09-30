from pathlib import Path

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field


class LLMConfig(BaseModel):
    model_name: str
    base_url: AnyHttpUrl
    api_key_env: str
    temperature: float = 0.7
    max_completion_tokens: int = Field(ge=1, le=1024)
    max_retries: int = Field(ge=2, le=4)


def load_llm_config(path: Path) -> LLMConfig:
    with path.open() as config_file:
        config_data = yaml.safe_load(config_file)

    return LLMConfig.model_validate(config_data)
