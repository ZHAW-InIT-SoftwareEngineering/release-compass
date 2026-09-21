from pathlib import Path
from typing import Literal

import yaml
from pydantic import AnyUrl, BaseModel, Field


class LLMConfig(BaseModel):
    provider: Literal["vLLM", "openrouter"]
    model_name: Literal[
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "openrouter/free"
        ]
    base_url: AnyUrl | None = None
    temperature: float = 0.7
    max_tokens: int = Field(ge=1, le=1024)
    max_retries: int = Field(ge=2, le=4) 


def load_llm_config(path: Path) -> LLMConfig:
    with path.open() as config_file:
        config_data = yaml.safe_load(config_file)

    return LLMConfig.model_validate(config_data)