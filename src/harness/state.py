"""State carried by the harness graph."""

from langgraph.graph import MessagesState


class HarnessState(MessagesState):
    """Conversation state plus whether CI/CD was already triggered."""

    cicd_triggered: bool = False
