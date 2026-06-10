from __future__ import annotations

import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_upstage import ChatUpstage
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

from agent.src.graph.state import AgentState
from agent.src.tool import tools

load_dotenv()


# ---------------------------------------------------------------------
# LLM rate limiting
# ---------------------------------------------------------------------
# Solar/Upstage 쪽 RPM/RTM 제한을 피하기 위해 프로세스 내 모든 LLM 요청 사이에
# 최소 4초 간격을 둔다.
LLM_MIN_INTERVAL_SECONDS = 4.0
LLM_RATE_LOCK = threading.Lock()
LAST_LLM_REQUEST_AT = 0.0

# 429 / Too Many Requests 발생 시 추가 대기 후 재시도
RATE_LIMIT_DELAYS = (10, 30, 60, 120)
MAX_NO_TOOL_RECOVERY_ATTEMPTS = 3
MAX_DESIGN_RETRY_ATTEMPTS = 3


BASE_CONTEXT = """You are an elite, autonomous Machine Learning Agent.

[ENVIRONMENT & CONTEXT]
- Project ID: {project_id}
- User ID: {u_id}
- Hypothesis ID: {hypothesis_id}
- Hypothesis Directory: {hypothesis_dir}
- Experiment ID: {exp_id}
- Experiment Directory: {exp_dir}
- Experiment YAML: {experiment_yml}
- Repository Root: {project_root}
- Path Rules: {path_rules_path}
- Assigned Variation: {variation_instruction}

[GLOBAL TOOL RULES]
- DO NOT output tool calls as raw text or XML such as <tool_call>...</tool_call>.
- You MUST use the proper JSON function calling API.
- Make exactly ONE tool call at a time, wait for the response, then continue.
- Use update_status before each meaningful phase.
- Tool arguments MUST be JSON objects.
- Read the path rules from exactly `{path_rules_path}`. Never resolve it relative
  to the hypothesis or experiment directory.
- Do not claim completion until the required files physically exist.
"""


DESIGN_PROMPT = BASE_CONTEXT + """

[CURRENT PHASE: DESIGN ONLY]

Your task is ONLY to design this experiment.

You MUST:
1. Read exactly `{path_rules_path}`.
2. Read the hypothesis YAML:
   `data/projects/{project_id}/hypotheses/{hypothesis_id}/{u_id}_{hypothesis_id}.yml`
3. Read the data description if it exists:
   `data/projects/{project_id}/data_description.txt`
4. Read the existing experiment YAML:
   `{experiment_yml}`
5. Update the existing experiment YAML at exactly:
   `{experiment_yml}`

You must fill or update ONLY these fields inside the `design` section:

- design.experiment_text
- design.model
- design.features
- design.hyperparameters

You MUST preserve:
- hypothesis_id
- exp_id
- design.formula

You MUST use the assigned variation to make this design distinct:
{variation_instruction}

`design.hyperparameters` may be an empty mapping when the plan intentionally uses model defaults.

Do NOT:
- create design.yml
- create a new YAML file
- perform EDA
- write eda.py
- train a model
- write train.py
- write report.md
- set status=done

When beginning, call update_status with:
- status: "running"
- current_task: "실험 설계 중"

When the experiment YAML has been updated successfully, stop.
"""


EXECUTION_PROMPT = BASE_CONTEXT + """

[CURRENT PHASE: EXECUTION ONLY]

The experiment design has already been written into:
{experiment_yml}

Your task is to perform ONLY:
1. EDA
2. Training and evaluation
3. Final report

Do NOT redesign the experiment.

You MUST:
1. Read exactly `{path_rules_path}`.
2. Read the hypothesis YAML:
   `data/projects/{project_id}/hypotheses/{hypothesis_id}/{u_id}_{hypothesis_id}.yml`
3. Read the experiment YAML:
   `{experiment_yml}`
4. Read the data description if it exists:
   `data/projects/{project_id}/data_description.txt`

The evaluation formula is already defined in the experiment YAML under:
`design.formula`

You MUST use that formula as the ONLY evaluation metric.
Do not change it.

You MUST preserve:
- hypothesis_id
- exp_id
- design.formula
- design.experiment_text
- design.model
- design.features
- design.hyperparameters

[DATA RULES]
- The only model inputs are:
  - `data/projects/{project_id}/train.csv`
  - `data/projects/{project_id}/test.csv`
- Read CSV files with pandas.
- Do not use `project.db`.
- Do not generate SQL.
- NEVER call read_file for a CSV.
- If you need to inspect CSVs, use execute_command with a short pandas summary limited to:
  shape, columns, dtypes, missing counts, descriptive statistics, or head().

[EDA REQUIREMENTS]
1. Call update_status with:
   - status: "running"
   - current_task: "EDA 진행 중"

2. Write EDA code exactly to:
   `{exp_dir}/eda.py`

3. Execute exactly:
   `python {exp_dir}/eda.py --train-path data/projects/{project_id}/train.csv --test-path data/projects/{project_id}/test.csv`

4. The EDA script must resolve the image directory using:
   `Path(__file__).resolve().parent / "img"`

5. Save real visualizations to:
   `{exp_dir}/img/`

6. A placeholder file such as `.keep` is not a valid artifact.

7. The image directory must contain at least one non-empty PNG, JPG, JPEG, or WEBP file.

[TRAINING REQUIREMENTS]
1. Call update_status with:
   - status: "running"
   - current_task: "모델 학습 중"

2. Write training code exactly to:
   `{exp_dir}/train.py`

3. Execute it with:
   `--train-path data/projects/{project_id}/train.csv`
   `--test-path data/projects/{project_id}/test.csv`
   `--mlflow-uri sqlite:///{hypothesis_dir}/mlflow.db`

4. The project test.csv may not contain the target.
   Create a validation split from train.csv and calculate the score on that held-out split.

5. Use ONLY the formula from `design.formula`.

6. Write the numeric score by calling update_status with:
   - status: "running"
   - current_task: "모델 학습 완료"
   - score: numeric score

[REPORT REQUIREMENTS]
1. Call update_status with:
   - status: "running"
   - current_task: "보고서 작성 중"

2. Write report exactly to:
   `{exp_dir}/report.md`

3. Use relative image paths, for example:
   `![caption](img/chart.png)`

4. Finally call update_status with:
   - status: "done"
   - current_task: "실험 완료"
   - score: numeric score
   - analysis_text: concise final analysis

Remember:
- Execute the Python scripts using execute_command.
- Fix execution errors before continuing.
- Do not claim completion until `eda.py`, `train.py`, `report.md`, and image artifacts physically exist.
"""


@lru_cache(maxsize=1)
def get_llm_with_tools():
    """Initialize the tool-bound model once per process."""
    return ChatUpstage(model="solar-pro").bind_tools(tools)


def _wait_for_llm_rate_limit() -> None:
    """Ensure at least LLM_MIN_INTERVAL_SECONDS between LLM requests."""
    global LAST_LLM_REQUEST_AT

    with LLM_RATE_LOCK:
        now = time.monotonic()
        elapsed = now - LAST_LLM_REQUEST_AT
        wait_seconds = LLM_MIN_INTERVAL_SECONDS - elapsed

        if wait_seconds > 0:
            time.sleep(wait_seconds)

        LAST_LLM_REQUEST_AT = time.monotonic()


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return whether an LLM failure is likely a retryable rate-limit response."""
    message = str(exc).lower()
    return (
        "429" in message
        or "too_many_requests" in message
        or "too many requests" in message
        or "rate limit" in message
        or "resource_exhausted" in message
        or "quota" in message
        or "rpm" in message
        or "rtm" in message
    )


def _invoke_with_retry(chain, payload: dict):
    """Invoke LLM with fixed inter-request spacing and retry on rate limits."""
    for attempt in range(len(RATE_LIMIT_DELAYS) + 1):
        try:
            _wait_for_llm_rate_limit()
            return chain.invoke(payload)

        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == len(RATE_LIMIT_DELAYS):
                raise

            delay = RATE_LIMIT_DELAYS[attempt]
            time.sleep(delay)

    # 여기까지 도달하지 않아야 하지만 타입/린터 안정성을 위해 둔다.
    raise RuntimeError("LLM invocation failed after retries")


def _state_get(state: AgentState, key: str, default: Any = None) -> Any:
    """Safely read both dict-style and TypedDict-style state values."""
    try:
        return state.get(key, default)
    except AttributeError:
        return default


def _resolve_exp_id(state: AgentState) -> str:
    """Resolve exp_id from state, falling back to exp_dir name."""
    exp_id = _state_get(state, "exp_id")
    if exp_id:
        return str(exp_id)

    exp_dir = str(state["exp_dir"])
    return os.path.basename(os.path.normpath(exp_dir))


def _resolve_experiment_yml(state: AgentState) -> str:
    """Resolve experiment YAML path.

    Preferred order:
    1. state["experiment_yml"]
    2. {exp_dir}/{exp_id}.yml
    3. {exp_dir}/exp_id.yml
    """
    experiment_yml = _state_get(state, "experiment_yml")
    if experiment_yml:
        return str(experiment_yml)

    exp_dir = Path(str(state["exp_dir"]))
    exp_id = _resolve_exp_id(state)

    preferred = exp_dir / f"{exp_id}.yml"
    legacy = exp_dir / "exp_id.yml"

    if preferred.exists():
        return str(preferred)

    return str(legacy)


def _resolve_variation_instruction(state: AgentState) -> str:
    """Resolve variation instruction for this experiment."""
    variation_instruction = _state_get(state, "variation_instruction")
    if variation_instruction:
        return str(variation_instruction)

    return (
        "Create a strong, distinct experiment design while preserving the "
        "evaluation formula and hypothesis."
    )


def _agent_node(state: AgentState, system_prompt: str) -> dict:
    """Run one ReAct turn with the selected system prompt."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = prompt | get_llm_with_tools()

    exp_id = _resolve_exp_id(state)
    experiment_yml = _resolve_experiment_yml(state)
    variation_instruction = _resolve_variation_instruction(state)

    payload = {
        "project_root": str(Path(__file__).resolve().parents[3]),
        "path_rules_path": str(
            Path(__file__).resolve().parents[3] / "shared" / "templates" / "path_rules.md"
        ),
        "project_id": state["project_id"],
        "u_id": _state_get(state, "u_id", "demo_user"),
        "hypothesis_id": state["hypothesis_id"],
        "hypothesis_dir": state["hypothesis_dir"],
        "exp_dir": state["exp_dir"],
        "exp_id": exp_id,
        "experiment_yml": experiment_yml,
        "variation_instruction": variation_instruction,
        "messages": state["messages"],
    }

    response = _invoke_with_retry(chain, payload)

    return {"messages": [response]}


def design_agent_node(state: AgentState) -> dict:
    """Agent node for the design-only graph."""
    return _agent_node(state, DESIGN_PROMPT)


def execution_agent_node(state: AgentState) -> dict:
    """Agent node for the EDA/train/report graph."""
    return _agent_node(state, EXECUTION_PROMPT)


def _has_tool_calls(state: AgentState) -> bool:
    """Return whether the latest model response contains real tool calls."""
    messages = state.get("messages") or []
    if not messages:
        return False
    return bool(getattr(messages[-1], "tool_calls", None))


def _execution_is_complete(state: AgentState) -> bool:
    """Return whether status and required execution artifacts are complete."""
    exp_dir = Path(str(state["exp_dir"]))
    status_path = exp_dir / "status.yml"
    try:
        status = yaml.safe_load(status_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return False
    required = ("eda.py", "train.py", "report.md")
    return status.get("status") == "done" and all(
        (exp_dir / filename).is_file() for filename in required
    )


def design_validation_errors(state: AgentState) -> list[str]:
    """Validate the persisted design before allowing the design graph to end."""
    experiment_yml = Path(_resolve_experiment_yml(state))
    try:
        experiment = yaml.safe_load(experiment_yml.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return ["experiment YAML is unreadable"]

    errors: list[str] = []
    exp_id = _resolve_exp_id(state)
    if experiment.get("exp_id") not in {None, exp_id}:
        errors.append("exp_id was changed")

    design = experiment.get("design")
    if not isinstance(design, dict):
        return errors + ["design must be a mapping"]

    for field in ("experiment_text", "model", "features"):
        if design.get(field) in (None, "", [], {}):
            errors.append(f"design.{field} is empty")

    if not isinstance(design.get("hyperparameters"), dict):
        errors.append("design.hyperparameters must be a mapping")

    expected_formula = state.get("evaluation_formula")
    if expected_formula and design.get("formula") != expected_formula:
        errors.append("design.formula was changed")

    return errors


def route_after_agent(
    state: AgentState,
    *,
    require_done: bool,
    validate_design: bool = False,
) -> str:
    """Route model output, recovering when it narrates a tool call as plain text."""
    if _has_tool_calls(state):
        return "tools"
    if validate_design:
        if not design_validation_errors(state):
            return "end"
        if int(state.get("design_retry_attempts", 0)) >= MAX_DESIGN_RETRY_ATTEMPTS:
            return "end"
        return "recover_design"
    if not require_done or _execution_is_complete(state):
        return "end"
    if int(state.get("no_tool_attempts", 0)) >= MAX_NO_TOOL_RECOVERY_ATTEMPTS:
        return "end"
    return "recover"


def recover_missing_tool_call(state: AgentState) -> dict:
    """Tell the model to issue the intended operation as an actual tool call."""
    attempts = int(state.get("no_tool_attempts", 0)) + 1
    return {
        "messages": [
            HumanMessage(
                content=(
                    "Your previous response described the next action but did not "
                    "call a tool. Continue the execution workflow now. Make exactly "
                    "one real JSON tool call for the next required action. Do not "
                    "narrate or summarize the intended call."
                )
            )
        ],
        "no_tool_attempts": attempts,
    }


def recover_invalid_design(state: AgentState) -> dict:
    """Ask the design agent to repair missing or invalid persisted fields."""
    attempts = int(state.get("design_retry_attempts", 0)) + 1
    errors = design_validation_errors(state)
    return {
        "messages": [
            HumanMessage(
                content=(
                    "The persisted experiment design did not pass validation. "
                    f"Problems: {'; '.join(errors)}. Read the existing experiment "
                    "YAML and repair it at the exact same path. Preserve exp_id, "
                    "hypothesis_id, and design.formula. Make exactly one real JSON "
                    "tool call now; do not merely describe the fix."
                )
            )
        ],
        "design_retry_attempts": attempts,
    }


def reset_missing_tool_call_recovery(state: AgentState) -> dict:
    """Reset consecutive recovery attempts after a successful tool call."""
    return {"no_tool_attempts": 0}


def _build_single_agent_graph(
    agent_node,
    *,
    require_done: bool,
    validate_design: bool = False,
):
    """Build a simple ReAct graph: agent -> tools -> agent."""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("recover", recover_missing_tool_call)
    workflow.add_node("recover_design", recover_invalid_design)
    workflow.add_node("reset_recovery", reset_missing_tool_call_recovery)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        lambda state: route_after_agent(
            state,
            require_done=require_done,
            validate_design=validate_design,
        ),
        {
            "tools": "tools",
            "recover": "recover",
            "recover_design": "recover_design",
            "end": END,
        },
    )
    workflow.add_edge("tools", "reset_recovery")
    workflow.add_edge("reset_recovery", "agent")
    workflow.add_edge("recover", "agent")
    workflow.add_edge("recover_design", "agent")

    return workflow.compile()


def build_design_graph():
    """Build graph that only fills the experiment design section."""
    return _build_single_agent_graph(
        design_agent_node,
        require_done=False,
        validate_design=True,
    )


def build_execution_graph():
    """Build graph that runs EDA, training, evaluation, and report."""
    return _build_single_agent_graph(execution_agent_node, require_done=True)


def build_graph():
    """Backward-compatible default graph.

    Existing runner or LangGraph Studio calls to build_graph() will run the
    execution graph. Use build_design_graph() explicitly for the design phase.
    """
    return build_execution_graph()


# For LangGraph Studio compatibility
graph = build_graph()
