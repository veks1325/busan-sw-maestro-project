from pathlib import Path

import yaml
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.src.graph.main_graph import (
    BASE_CONTEXT,
    DESIGN_PROMPT,
    EXECUTION_PROMPT,
    RATE_LIMIT_DELAYS,
    _execution_is_complete,
    _is_rate_limit_error,
    _resolve_experiment_yml,
    design_validation_errors,
)


def _state(tmp_path: Path) -> dict:
    exp_dir = tmp_path / "exp-1"
    exp_dir.mkdir()
    experiment_yml = exp_dir / "exp-1.yml"
    experiment_yml.write_text(
        yaml.safe_dump(
            {
                "hypothesis_id": "hyp-1",
                "exp_id": "exp-1",
                "design": {"formula": "R2 Score"},
                "score": None,
            }
        ),
        encoding="utf-8",
    )
    return {
        "messages": [AIMessage(content="complete")],
        "project_id": "project-1",
        "u_id": "user-1",
        "hypothesis_id": "hyp-1",
        "hypothesis_dir": str(tmp_path),
        "exp_id": "exp-1",
        "exp_dir": str(exp_dir),
        "experiment_yml": str(experiment_yml),
        "variation_instruction": "baseline",
        "evaluation_formula": "R2 Score",
    }


def _write_valid_design(state: dict) -> None:
    Path(state["experiment_yml"]).write_text(
        yaml.safe_dump(
            {
                "hypothesis_id": "hyp-1",
                "exp_id": "exp-1",
                "design": {
                    "experiment_text": "baseline",
                    "model": "RandomForestRegressor",
                    "features": ["feature"],
                    "hyperparameters": {},
                    "formula": "R2 Score",
                },
                "score": None,
            }
        ),
        encoding="utf-8",
    )


def test_design_validation_accepts_default_hyperparameters(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _write_valid_design(state)

    assert design_validation_errors(state) == []


def test_design_validation_rejects_missing_fields(tmp_path: Path) -> None:
    state = _state(tmp_path)

    errors = design_validation_errors(state)

    assert "design.experiment_text is empty" in errors
    assert "design.model is empty" in errors
    assert "design.features is empty" in errors
    assert "design.hyperparameters must be a mapping" in errors


def test_design_validation_preserves_formula(tmp_path: Path) -> None:
    state = _state(tmp_path)
    _write_valid_design(state)
    experiment = yaml.safe_load(
        Path(state["experiment_yml"]).read_text(encoding="utf-8")
    )
    experiment["design"]["formula"] = "RMSE"
    Path(state["experiment_yml"]).write_text(
        yaml.safe_dump(experiment), encoding="utf-8"
    )

    assert "design.formula was changed" in design_validation_errors(state)


def test_resolve_experiment_yml_prefers_state_path(tmp_path: Path) -> None:
    state = _state(tmp_path)

    assert _resolve_experiment_yml(state) == state["experiment_yml"]


def test_resolve_experiment_yml_supports_legacy_filename(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp-legacy"
    exp_dir.mkdir()
    legacy_path = exp_dir / "exp_id.yml"
    legacy_path.write_text("exp_id: exp-legacy\n", encoding="utf-8")
    state = {"exp_dir": str(exp_dir), "exp_id": "exp-legacy"}

    assert _resolve_experiment_yml(state) == str(legacy_path)


def test_execution_completion_requires_status_and_artifacts(tmp_path: Path) -> None:
    state = _state(tmp_path)
    exp_dir = Path(state["exp_dir"])
    for filename in ("eda.py", "train.py", "report.md"):
        (exp_dir / filename).write_text("complete", encoding="utf-8")
    (exp_dir / "status.yml").write_text(
        yaml.safe_dump({"status": "done"}), encoding="utf-8"
    )

    assert _execution_is_complete(state) is True

    (exp_dir / "report.md").unlink()
    assert _execution_is_complete(state) is False


def test_upstage_rate_limit_errors_are_retryable() -> None:
    assert _is_rate_limit_error(RuntimeError("429 too_many_requests")) is True
    assert _is_rate_limit_error(RuntimeError("resource_exhausted quota")) is True
    assert _is_rate_limit_error(RuntimeError("invalid request")) is False


def test_rate_limit_backoff_has_long_cooldown() -> None:
    assert RATE_LIMIT_DELAYS == (10, 30, 60, 120)


def test_prompts_format_without_unresolved_template_variables() -> None:
    payload = {
        "project_root": "/workspace/hypoloop",
        "path_rules_path": "/workspace/hypoloop/shared/templates/path_rules.md",
        "project_id": "project-1",
        "u_id": "user-1",
        "hypothesis_id": "hypothesis-1",
        "hypothesis_dir": "/workspace/hypothesis-1",
        "exp_id": "experiment-1",
        "exp_dir": "/workspace/experiment-1",
        "experiment_yml": "/workspace/experiment-1/experiment-1.yml",
        "variation_instruction": "baseline",
        "messages": [],
    }

    for system_prompt in (BASE_CONTEXT, DESIGN_PROMPT, EXECUTION_PROMPT):
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), MessagesPlaceholder(variable_name="messages")]
        )
        formatted = prompt.invoke(payload)
        assert "project-1" in formatted.messages[0].content
