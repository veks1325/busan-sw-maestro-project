from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    project_id: str
    u_id: str
    hypothesis_id: str
    hypothesis_dir: str
    exp_dir: str
