from langchain.tools import tool

@tool
def addition(a, b):
    """Add two numbers and return their sum.

    Use this tool when the user asks to add two numeric values. The arguments
    are the first and second addends; the result is their arithmetic sum.
    """
    return a + b
