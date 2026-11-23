from pathlib import Path

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field


class GitHubDispatchConfig(BaseModel):
    api_url: AnyHttpUrl = AnyHttpUrl("https://api.github.com")
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    token_env: str = Field(min_length=1)
    timeout_seconds: float = Field(default=10, gt=0)


def load_github_dispatch_config(path: Path) -> GitHubDispatchConfig:
    with path.open() as config_file:
        config_data = yaml.safe_load(config_file)

    return GitHubDispatchConfig.model_validate(config_data)
