from langchain.messages import HumanMessage
from pathlib import Path

from .configs.llm_config import load_llm_config
from .llm.llm import init_llm
from .harness.tools.calculation import (
    addition
)

def main(): 
    LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")
    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)

    llm.bind_tools([addition])

    messages = [HumanMessage(content="Add 3 and 4.")]

    response = llm.invoke(
        messages
    )

    print(f"reponse:\n{response}")



if __name__ == "__main__": 
    main()