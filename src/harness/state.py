"""State carried by the harness graph."""

from langgraph.graph import MessagesState


class HarnessState(MessagesState):
    """Conversation state plus the user's CI/CD trigger approval decision."""

    approved_cicd: bool
