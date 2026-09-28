from pathlib import Path

from langchain_openai import ChatOpenAI

from ..configs.llm_config import LLMConfig


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _read_env_file(name: str) -> str | None:
    if not _ENV_FILE.is_file():
        return None

    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.removeprefix("export ").strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


def init_llm(llm_config: LLMConfig) -> ChatOpenAI:
    api_key = _read_env_file(llm_config.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Missing {llm_config.api_key_env} in {_ENV_FILE}"
        )

    return ChatOpenAI(
        model=llm_config.model_name,
        base_url=str(llm_config.base_url),
        api_key=api_key,
        temperature=llm_config.temperature,
        max_completion_tokens=llm_config.max_completion_tokens,
        max_retries=llm_config.max_retries,
    )
