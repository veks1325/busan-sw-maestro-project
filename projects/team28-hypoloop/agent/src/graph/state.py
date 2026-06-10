from typing import Annotated, Literal, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    project_id: str
    u_id: str
    hypothesis_id: str
    hypothesis_dir: str
    exp_id: str
    exp_dir: str
    experiment_yml: str
    experiment_index: int
    experiment_total: int
    variation_instruction: str
    evaluation_formula: str
    stage: Literal["design", "eda", "train", "report"]
    stage_attempts: dict[str, int]
    stage_tool_calls: dict[str, int]
    no_tool_attempts: int
    design_retry_attempts: int
    stage_result: Literal[
        "continue", "validate", "next", "retry", "complete", "failed"
    ]
