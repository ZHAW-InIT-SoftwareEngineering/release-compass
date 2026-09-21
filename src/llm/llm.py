from langchain_openrouter import ChatOpenRouter

from ..configs import LLMConfig


def init_llm(llm_config: LLMConfig):
    match llm_config.provider: 
        case "openrouter":
            return create_openrouter_model(llm_config)

        case _:
            raise ValueError(f"Unsupported LLM provider: {llm_config.provider}")        




def create_openrouter_model(llm_config):
    return ChatOpenRouter(
        model=llm_config.model_name,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_token,
        max_retries=llm_config.max_retries
    )