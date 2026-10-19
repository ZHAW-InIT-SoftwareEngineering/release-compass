"""State carried by the harness graph."""

from langgraph.graph import MessagesState


class HarnessState(MessagesState):
    """Conversation state plus the user's CI/CD trigger approval decision."""

    cicd_triggered: bool = False
    user_approved_cicd: bool = False
