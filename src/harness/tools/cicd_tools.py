from langchain.tools import tool


@tool
def cicd_tool() -> str:
    """Simulate triggering the CI/CD deployment workflow."""
    print("CI/CD Tool")
    return "CI/CD triggered"
