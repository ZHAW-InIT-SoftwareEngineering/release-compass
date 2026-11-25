from langchain_openai import ChatOpenAI

from src.configs.env import ENV_FILE, read_env_file
from src.configs.llm.llm_config import LLMConfig

_ENV_FILE = ENV_FILE


def init_llm(llm_config: LLMConfig) -> ChatOpenAI:
    api_key = read_env_file(llm_config.api_key_env, _ENV_FILE)
    if not api_key:
        raise RuntimeError(f"Missing {llm_config.api_key_env} in {_ENV_FILE}")

    return ChatOpenAI(
        model=llm_config.model_name,
        base_url=str(llm_config.base_url),
        api_key=api_key,
        temperature=llm_config.temperature,
        max_completion_tokens=llm_config.max_completion_tokens,
        max_retries=llm_config.max_retries,
    )
