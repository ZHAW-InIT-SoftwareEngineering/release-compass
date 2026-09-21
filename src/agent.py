from configs.llm_config import load_llm_config
from llm.llm import init_llm

def main(): 
    LLM_CONFIG_PATH = "../configs/llm/free.yaml"
    llm_config = load_llm_config(LLM_CONFIG_PATH)
    llm = init_llm(llm_config)



if __name__ == "__main__": 
    main()