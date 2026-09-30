from langchain.messages import HumanMessage
from pathlib import Path

from .configs.llm_config import load_llm_config
from .llm.llm import init_llm
from .harness.tools.calculation import (
    addition
)

from .application.ports.outbound.report_ingestion import ReportIngestionPort
from .adapters.outbound.html_report import HTMLReport


HTML_REPORT_PATH = Path("data/raw/reports/example_reports/report.html")
LLM_CONFIG_PATH = Path("configs/llm/openrouter.yaml")


def main(): 

    report_ingestion: ReportIngestionPort = HTMLReport()
    report = report_ingestion.ingest(HTML_REPORT_PATH)


    # print(f"report:\n{report}")
    


    
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