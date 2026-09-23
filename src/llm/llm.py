import os

from langchain_openai import ChatOpenAI

from ..configs.llm_config import LLMConfig


def init_llm(llm_config: LLMConfig) -> ChatOpenAI:
    api_key = os.getenv(llm_config.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Missing required environment variable: {llm_config.api_key_env}"
        )

    return ChatOpenAI(
        model=llm_config.model_name,
        base_url=str(llm_config.base_url),
        api_key=api_key,
        temperature=llm_config.temperature,
        max_completion_tokens=llm_config.max_completion_tokens,
        max_retries=llm_config.max_retries,
    )
