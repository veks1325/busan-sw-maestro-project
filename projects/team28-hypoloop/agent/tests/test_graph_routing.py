from pathlib import Path

import yaml
from langchain_core.messages import AIMessage

from agent.src.graph.main_graph import (
    MAX_DESIGN_RETRY_ATTEMPTS,
    MAX_NO_TOOL_RECOVERY_ATTEMPTS,
    design_validation_errors,
    recover_invalid_design,
    recover_missing_tool_call,
    reset_missing_tool_call_recovery,
    route_after_agent,
)


def _state(tmp_path: Path, message: AIMessage) -> dict:
    return {
        "messages": [message],
        "exp_dir": str(tmp_path),
        "exp_id": tmp_path.name,
        "experiment_yml": str(tmp_path / f"{tmp_path.name}.yml"),
        "evaluation_formula": "R2 Score",
        "no_tool_attempts": 0,
        "design_retry_attempts": 0,
    }


def test_execution_recovers_plain_text_instead_of_ending(tmp_path: Path) -> None:
    state = _state(tmp_path, AIMessage(content="Write EDA script next"))

    assert route_after_agent(state, require_done=True) == "recover"


def test_real_tool_call_routes_to_tools(tmp_path: Path) -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"file_path": "eda.py", "content": "print('ok')"},
                "id": "call-1",
                "type": "tool_call",
            }
        ],
    )

    assert route_after_agent(_state(tmp_path, message), require_done=True) == "tools"


def test_completed_execution_can_end_without_tool_call(tmp_path: Path) -> None:
    for filename in ("eda.py", "train.py", "report.md"):
        (tmp_path / filename).write_text("complete", encoding="utf-8")
    (tmp_path / "status.yml").write_text(
        yaml.safe_dump({"status": "done"}),
        encoding="utf-8",
    )

    state = _state(tmp_path, AIMessage(content="Execution complete"))

    assert route_after_agent(state, require_done=True) == "end"


def test_recovery_is_bounded_and_resets_after_tool() -> None:
    state = {"messages": [], "no_tool_attempts": 0}
    for expected in range(1, MAX_NO_TOOL_RECOVERY_ATTEMPTS + 1):
        update = recover_missing_tool_call(state)
        assert update["no_tool_attempts"] == expected
        state.update(update)

    assert reset_missing_tool_call_recovery(state)["no_tool_attempts"] == 0


def test_design_graph_retries_when_required_fields_are_empty(tmp_path: Path) -> None:
    state = _state(tmp_path, AIMessage(content="Design complete"))
    Path(state["experiment_yml"]).write_text(
        yaml.safe_dump(
            {
                "exp_id": tmp_path.name,
                "design": {
                    "experiment_text": None,
                    "model": None,
                    "features": [],
                    "hyperparameters": {},
                    "formula": "R2 Score",
                },
            }
        ),
        encoding="utf-8",
    )

    assert route_after_agent(
        state,
        require_done=False,
        validate_design=True,
    ) == "recover_design"
    assert "design.model is empty" in design_validation_errors(state)

    update = recover_invalid_design(state)
    assert update["design_retry_attempts"] == 1
    assert "design.features is empty" in update["messages"][0].content


def test_design_graph_ends_only_after_valid_design(tmp_path: Path) -> None:
    state = _state(tmp_path, AIMessage(content="Design complete"))
    Path(state["experiment_yml"]).write_text(
        yaml.safe_dump(
            {
                "exp_id": tmp_path.name,
                "design": {
                    "experiment_text": "baseline experiment",
                    "model": "RandomForestRegressor",
                    "features": ["feature"],
                    "hyperparameters": {},
                    "formula": "R2 Score",
                },
            }
        ),
        encoding="utf-8",
    )

    assert route_after_agent(
        state,
        require_done=False,
        validate_design=True,
    ) == "end"


def test_design_retry_is_bounded(tmp_path: Path) -> None:
    state = _state(tmp_path, AIMessage(content="Design complete"))
    state["design_retry_attempts"] = MAX_DESIGN_RETRY_ATTEMPTS

    assert route_after_agent(
        state,
        require_done=False,
        validate_design=True,
    ) == "end"
