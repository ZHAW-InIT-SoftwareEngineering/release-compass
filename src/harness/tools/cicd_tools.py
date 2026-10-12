from langchain.tools import tool


@tool
def cicd_tool(): 
    print(f"CI/CD Tool")
    