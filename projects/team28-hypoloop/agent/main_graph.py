from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
import py_compile
import re
import time

import yaml
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_upstage import ChatUpstage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt import ToolNode

from agent.src.graph.state import AgentState
from agent.src.tool import tools, update_status

load_dotenv()

MAX_STAGE_ATTEMPTS = 4
MAX_STAGE_TOOL_CALLS = 16
RATE_LIMIT_DELAYS = (5, 10, 30, 60)
STAGES = ("design", "eda", "train", "report")

BASE_PROMPT = """You are an autonomous machine-learning experiment agent.
You are working in a staged ReAct workflow. Work ONLY on the current stage, use
real JSON tool calls, observe their results, and do not claim completion until
the required files physically exist.

[CONTEXT]
- Project ID: {project_id}
- Hypothesis ID: {hypothesis_id}
- Hypothesis directory: {hypothesis_dir}
- Experiment ID: {exp_id}
- Experiment directory: {exp_dir}
- Experiment YAML: {experiment_yml}
- Hypothesis YAML: data/projects/{project_id}/hypotheses/{hypothesis_id}/{u_id}_{hypothesis_id}.yml
- Experiment number: {experiment_index}/{experiment_total}
- Assigned variation: {variation_instruction}
- Evaluation formula: {evaluation_formula}

[SHARED RULES]
- Read and follow shared/templates/path_rules.md.
- Read the hypothesis YAML and data/projects/{project_id}/data_description.txt when present.
- The only model inputs are data/projects/{project_id}/train.csv and test.csv.
- Read CSV files with pandas. Do not use project.db or generate SQL.
- NEVER call read_file for a CSV. Use execute_command with a short pandas summary
  limited to shape, columns, dtypes, missing counts, descriptive statistics, or head().
- Preserve hypothesis_id, exp_id, and the exact evaluation formula in exp_id.yml.
- Keep generated code and artifacts inside {exp_dir}.
- Call update_status when beginning meaningful work in this stage.
- Use status=running for design, EDA, and training. NEVER set status=done before the report stage.
- Make exactly ONE tool call per response and wait for its result before the next call.
- Tool arguments MUST be JSON objects. Call execute_command using exactly
  execute_command({{"command": "python path/to/script.py --flag value"}}).
  NEVER use positional syntax such as execute_command("python ...").
"""

STAGE_PROMPTS = {
    "design": """[CURRENT STAGE: EXPERIMENT DESIGN]
Read the hypothesis and existing experiment YAML.

You must update the existing experiment YAML file exactly at:
{experiment_yml}

Do not create design.yml.
Do not create any new YAML file.

Fill these fields inside {experiment_yml}:
design.experiment_text
design.model
design.features
design.hyperparameters

Preserve:
hypothesis_id = {hypothesis_id}
exp_id = {exp_id}
design.formula = {evaluation_formula}

`design.hyperparameters` may be an empty mapping when the plan intentionally uses model defaults.

Do not perform EDA, training, or report writing yet.
""",
   "eda": """[CURRENT STAGE: EDA]

Read the approved experiment design and CSV data description.

REQUIRED SEQUENCE:

1. Write the EDA script exactly at:
   {exp_dir}/eda.py

2. After write_file succeeds, execute exactly:
   python {exp_dir}/eda.py --train-path data/projects/{project_id}/train.csv --test-path data/projects/{project_id}/test.csv

3. Fix any execution errors.

4. Re-run the script if necessary.

5. Ensure that:
   - {exp_dir}/eda.py exists
   - {exp_dir}/img exists
   - {exp_dir}/img contains at least one non-empty PNG or JPG file

The EDA stage is NOT complete after writing eda.py.

The EDA stage is complete ONLY after the script has been executed successfully and image artifacts exist.

Never stop after write_file.

Never claim completion until image files exist.

Never execute:
python agent/src/eda.py
python agent/src/*.py

There is no global EDA script.

The EDA script must live exactly at:
{exp_dir}/eda.py

Inside the script, resolve the image directory using:

Path(__file__).resolve().parent / "img"

Save real visualizations into:

{exp_dir}/img/

A placeholder file such as .keep is not a valid artifact.

Do not train the final model.
Do not write the report.
""",
    "train": """[CURRENT STAGE: TRAINING AND EVALUATION]
Read the approved design and EDA artifacts. Write {exp_dir}/train.py and execute it
with --train-path data/projects/{project_id}/train.csv, --test-path
data/projects/{project_id}/test.csv, and --mlflow-uri
sqlite:///{hypothesis_dir}/mlflow.db. Evaluate only with {evaluation_formula}.
The project test.csv may not contain the target. Create the validation split from
train.csv (for example with train_test_split), calculate the score on that held-out
split, and use test.csv only for optional final inference.
Write the numeric result to exp_id.yml by calling update_status with status=running
and score=<numeric score>. Fix execution errors before finishing this stage.
Do not write the final report yet.
""",
    "report": """[CURRENT STAGE: REPORT]
Read the experiment design, EDA artifacts, training output, and numeric score.
Write {exp_dir}/report.md with findings, score, and hypothesis conclusion. Use
relative image paths such as img/chart.png. Finally call update_status with
status=done, current_task='실험 완료', the numeric score, and analysis_text.
""",
}

STAGE_START_TASKS = {
    "design": "실험 설계 중",
    "eda": "EDA 진행 중",
    "train": "모델 학습 중",
    "report": "보고서 작성 중",
}


###@lru_cache(maxsize=1)
#def get_llm_with_tools():
#    """Initialize the tool-bound model only when an experiment runs."""
#    return ChatUpstage(model="solar-pro3").bind_tools(tools)
###
@lru_cache(maxsize=1)
def get_llm_with_tools():
    """Initialize the tool-bound model only when an experiment runs."""
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview-customtools",
        temperature=0,
    ).bind_tools(tools)

def _is_rate_limit_error(exc: Exception) -> bool:
    """Return whether an LLM failure is a retryable API rate-limit response."""
    message = str(exc).lower()
    return "429" in message or "too_many_requests" in message or "rate limit" in message


def _invoke_with_retry(chain, payload: dict, state: AgentState):
    """Retry transient LLM rate limits with bounded exponential backoff."""
    for attempt in range(len(RATE_LIMIT_DELAYS) + 1):
        try:
            return chain.invoke(payload)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == len(RATE_LIMIT_DELAYS):
                raise
            delay = RATE_LIMIT_DELAYS[attempt]
            update_status.invoke(
                {
                    "exp_dir": state["exp_dir"],
                    "current_task": f"API 요청 제한 대기 중 ({delay}초 후 재시도)",
                    "status": "running",
                    "analysis_text": "Upstage API rate limit encountered; retrying automatically.",
                }
            )
            time.sleep(delay)


def _agent_node(state: AgentState, stage: str) -> dict:
    """Run one ReAct turn using instructions scoped to a single stage."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", BASE_PROMPT + "\n" + STAGE_PROMPTS[stage]),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    chain = prompt | get_llm_with_tools()
    payload = {
        "project_id": state["project_id"],
        "u_id": state.get("u_id", "demo_user"),
        "hypothesis_id": state["hypothesis_id"],
        "hypothesis_dir": state["hypothesis_dir"],
        "exp_id": state["exp_id"],
        "exp_dir": state["exp_dir"],
        "experiment_yml": state["experiment_yml"],
        "experiment_index": state["experiment_index"],
        "experiment_total": state["experiment_total"],
        "variation_instruction": state["variation_instruction"],
        "evaluation_formula": state["evaluation_formula"],
        "messages": state["messages"],
    }
    response = _invoke_with_retry(chain, payload, state)
    return {"messages": [response], "stage": stage}


def design_agent(state: AgentState) -> dict:
    return _agent_node(state, "design")


def eda_agent(state: AgentState) -> dict:
    return _agent_node(state, "eda")


def train_agent(state: AgentState) -> dict:
    return _agent_node(state, "train")


def report_agent(state: AgentState) -> dict:
    return _agent_node(state, "report")


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _design_errors(state: AgentState) -> list[str]:
    errors: list[str] = []
    try:
        experiment = _load_yaml(Path(state["experiment_yml"]))
        if experiment.get("hypothesis_id") != state["hypothesis_id"]:
            errors.append("hypothesis_id was changed")
        if experiment.get("exp_id") != state["exp_id"]:
            errors.append("exp_id was changed")
        design = experiment.get("design") or {}
        for field in ("experiment_text", "model", "features"):
            if design.get(field) in (None, "", [], {}):
                errors.append(f"design.{field} is empty")
        if not isinstance(design.get("hyperparameters"), dict):
            errors.append("design.hyperparameters must be a mapping")
        if design.get("formula") != state["evaluation_formula"]:
            errors.append("design.formula was changed")
    except (OSError, yaml.YAMLError):
        errors.append("experiment YAML is unreadable")
    return errors


def _eda_errors(state: AgentState) -> list[str]:
    exp_dir = Path(state["exp_dir"])
    errors = []
    eda_path = exp_dir / "eda.py"
    if not eda_path.is_file():
        errors.append("missing eda.py")
    else:
        try:
            py_compile.compile(str(eda_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"eda.py has invalid Python syntax: {exc.msg}")
    image_dir = exp_dir / "img"
    if not image_dir.is_dir():
        errors.append("missing img directory")
    elif not any(
        path.is_file()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        and path.stat().st_size > 0
        for path in image_dir.rglob("*")
    ):
        errors.append("EDA produced no image artifacts")
    return errors


def _train_errors(state: AgentState) -> list[str]:
    errors = []
    train_path = Path(state["exp_dir"]) / "train.py"
    if not train_path.is_file():
        errors.append("missing train.py")
    else:
        try:
            py_compile.compile(str(train_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"train.py has invalid Python syntax: {exc.msg}")
    try:
        experiment = _load_yaml(Path(state["experiment_yml"]))
        if not isinstance(experiment.get("score"), (int, float)):
            errors.append("experiment score is not numeric")
        if (experiment.get("design") or {}).get("formula") != state["evaluation_formula"]:
            errors.append("design.formula was changed")
    except (OSError, yaml.YAMLError):
        errors.append("experiment YAML is unreadable")
    return errors


def _report_errors(state: AgentState) -> list[str]:
    exp_dir = Path(state["exp_dir"])
    errors = []
    if not (exp_dir / "report.md").is_file():
        errors.append("missing report.md")
    try:
        status = _load_yaml(exp_dir / "status.yml")
        if status.get("status") != "done":
            errors.append("status.yml status is not done")
    except (OSError, yaml.YAMLError):
        errors.append("status.yml is unreadable")
    errors.extend(_design_errors(state))
    errors.extend(_eda_errors(state))
    errors.extend(_train_errors(state))
    return errors


STAGE_VALIDATORS = {
    "design": _design_errors,
    "eda": _eda_errors,
    "train": _train_errors,
    "report": _report_errors,
}


def route_after_stage_agent(state: AgentState) -> str:
    """Send tool calls to ToolNode and plain responses to stage validation."""
    last_message = state["messages"][-1]
    return "tools" if getattr(last_message, "tool_calls", None) else "validate"


_POSITIONAL_COMMAND_PATTERN = re.compile(
    r"<tool_call>\s*\[?execute_command\((.*?)\)\]?\s*</tool_call>",
    re.DOTALL,
)


def _extract_positional_commands(content: object) -> list[str]:
    """Recover commands emitted in the model's unsupported positional syntax."""
    if not isinstance(content, str):
        return []
    commands = []
    for raw_argument in _POSITIONAL_COMMAND_PATTERN.findall(content):
        try:
            value = ast.literal_eval(raw_argument.strip())
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, str) and value.strip():
            commands.append(value)
    return commands


def normalize_tool_calls(state: AgentState) -> dict:
    """Repair execute_command calls whose positional argument became empty args."""
    message = state["messages"][-1]
    commands = iter(_extract_positional_commands(message.content))
    repaired_calls = []
    changed = False
    for call in message.tool_calls:
        repaired = dict(call)
        args = repaired.get("args") or {}
        if repaired.get("name") == "execute_command" and not args.get("command"):
            command = next(commands, None)
            if command is not None:
                repaired["args"] = {"command": command}
                changed = True
        repaired_calls.append(repaired)

    if not changed:
        return {}
    return {"messages": [message.model_copy(update={"tool_calls": repaired_calls})]}


def check_stage_after_tools(state: AgentState) -> dict:
    """Validate completed artifacts after every tool call and bound tool loops."""
    stage = state["stage"]
    counts = dict(state.get("stage_tool_calls", {}))
    counts[stage] = counts.get(stage, 0) + 1
    errors = STAGE_VALIDATORS[stage](state)
    if not errors:
        result = "validate"
    elif counts[stage] >= MAX_STAGE_TOOL_CALLS:
        result = "failed"
    else:
        result = "continue"
    return {"stage_tool_calls": counts, "stage_result": result}


def route_after_tool_check(state: AgentState) -> str:
    """Advance a completed stage, continue work, or stop a runaway tool loop."""
    if state["stage_result"] == "validate":
        return f"validate_{state['stage']}"
    if state["stage_result"] == "failed":
        return "failed"
    return f"{state['stage']}_agent"


def _validate_stage(state: AgentState, stage: str) -> dict:
    """Advance only when the current stage's physical artifacts are valid."""
    errors = STAGE_VALIDATORS[stage](state)
    attempts = dict(state.get("stage_attempts", {}))
    if errors:
        attempts[stage] = attempts.get(stage, 0) + 1
        result = "failed" if attempts[stage] >= MAX_STAGE_ATTEMPTS else "retry"
        return {
            "messages": [
                HumanMessage(
                    content=(
                        f"{stage} stage is incomplete. Continue only this stage and "
                        "use actual tool calls. Invalid: " + "; ".join(errors)
                    )
                )
            ],
            "stage": stage,
            "stage_attempts": attempts,
            "stage_result": result,
        }

    if stage == "report":
        return {"stage": stage, "stage_attempts": attempts, "stage_result": "complete"}

    next_stage = STAGES[STAGES.index(stage) + 1]
    update_status.invoke(
        {
            "exp_dir": state["exp_dir"],
            "current_task": STAGE_START_TASKS[next_stage],
            "status": "running",
        }
    )
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            HumanMessage(
                content=f"{stage} stage passed validation. Begin only the {next_stage} stage."
            )
        ],
        "stage": next_stage,
        "stage_attempts": attempts,
        "stage_tool_calls": state.get("stage_tool_calls", {}),
        "stage_result": "next",
    }


def validate_design(state: AgentState) -> dict:
    return _validate_stage(state, "design")


def validate_eda(state: AgentState) -> dict:
    return _validate_stage(state, "eda")


def validate_train(state: AgentState) -> dict:
    return _validate_stage(state, "train")


def validate_report(state: AgentState) -> dict:
    return _validate_stage(state, "report")


def route_after_validation(state: AgentState) -> str:
    """Retry, advance, finish, or fail according to validator output."""
    if state["stage_result"] == "retry":
        return f"{state['stage']}_agent"
    if state["stage_result"] == "next":
        return f"{state['stage']}_agent"
    if state["stage_result"] == "complete":
        return "complete"
    return "failed"


def mark_failed(state: AgentState) -> dict:
    """Persist a terminal failure when a stage exhausts its retry budget."""
    stage = state["stage"]
    tool_calls = state.get("stage_tool_calls", {}).get(stage, 0)
    if tool_calls >= MAX_STAGE_TOOL_CALLS:
        message = (
            f"{stage} stage exceeded the tool-call limit "
            f"({MAX_STAGE_TOOL_CALLS}) without producing valid artifacts"
        )
    else:
        message = f"{stage} stage failed validation after {MAX_STAGE_ATTEMPTS} attempts"
    update_status.invoke(
        {
            "exp_dir": state["exp_dir"],
            "current_task": "실험 실패",
            "status": "failed",
            "analysis_text": message,
        }
    )
    return {"messages": [HumanMessage(content=message)]}


def build_graph():
    """Build four ordered ReAct loops with deterministic stage validation."""
    workflow = StateGraph(AgentState)
    tool_node = ToolNode(tools)

    for stage, agent in (
        ("design", design_agent),
        ("eda", eda_agent),
        ("train", train_agent),
        ("report", report_agent),
    ):
        agent_name = f"{stage}_agent"
        validator_name = f"validate_{stage}"
        validator = globals()[validator_name]
        workflow.add_node(agent_name, agent)
        workflow.add_node(validator_name, validator)
        workflow.add_conditional_edges(
            agent_name,
            route_after_stage_agent,
            {"tools": "normalize_tools", "validate": validator_name},
        )
        workflow.add_conditional_edges(
            validator_name,
            route_after_validation,
            {
                "design_agent": "design_agent",
                "eda_agent": "eda_agent",
                "train_agent": "train_agent",
                "report_agent": "report_agent",
                "complete": END,
                "failed": "failed",
            },
        )

    workflow.add_node("normalize_tools", normalize_tool_calls)
    workflow.add_node("tools", tool_node)
    workflow.add_node("check_stage", check_stage_after_tools)
    workflow.add_node("failed", mark_failed)
    workflow.add_edge(START, "design_agent")
    workflow.add_edge("tools", "check_stage")
    workflow.add_conditional_edges(
        "check_stage",
        route_after_tool_check,
        {
            **{f"{stage}_agent": f"{stage}_agent" for stage in STAGES},
            **{f"validate_{stage}": f"validate_{stage}" for stage in STAGES},
            "failed": "failed",
        },
    )
    workflow.add_edge("normalize_tools", "tools")
    workflow.add_edge("failed", END)
    return workflow.compile()


graph = build_graph()
