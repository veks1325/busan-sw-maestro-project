from __future__ import annotations

import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import yaml
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agent.src.graph.main_graph import build_design_graph, build_execution_graph
from agent.src.graph.preflight import ScreeningResult, screen_hypothesis
from agent.src.tool import update_status

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRINT_LOCK = threading.Lock()

VARIATION_PROFILES = (
    "Establish a strong baseline with conservative preprocessing and a simple, robust model.",
    "Focus on feature selection and feature engineering while keeping the evaluation formula unchanged.",
    "Try a different model family and tune model complexity to test whether the hypothesis generalizes.",
    "Focus on regularization and overfitting control with conservative hyperparameters.",
    "Focus on validation stability, missing-value handling, and robustness to noisy features.",
)


@dataclass(frozen=True)
class ExperimentJob:
    """One backend-created experiment assigned to the agent."""

    exp_id: str
    exp_dir: Path
    experiment_yml: Path
    index: int
    total: int
    variation_instruction: str


def load_hypothesis(hypothesis_file: Path) -> dict:
    """Load and validate the backend-created hypothesis configuration."""
    if not hypothesis_file.exists():
        raise FileNotFoundError(f"Hypothesis YML not found: {hypothesis_file}")

    with hypothesis_file.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    for field in ("content", "max_experiments", "parallel_count"):
        if field not in data:
            raise ValueError(f"Hypothesis YML is missing required field: {field}")

    max_experiments = int(data["max_experiments"])
    parallel_count = int(data["parallel_count"])

    if max_experiments < 1:
        raise ValueError("max_experiments must be at least 1")
    if parallel_count < 1:
        raise ValueError("parallel_count must be at least 1")

    data["max_experiments"] = max_experiments
    data["parallel_count"] = min(parallel_count, max_experiments)
    return data


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _experiment_yml_path(exp_dir: Path) -> Path | None:
    """Return the preferred experiment YAML path."""
    preferred_path = exp_dir / f"{exp_dir.name}.yml"
    legacy_path = exp_dir / "exp_id.yml"

    if preferred_path.exists():
        return preferred_path
    if legacy_path.exists():
        return legacy_path
    return None


def _is_runnable(exp_dir: Path) -> bool:
    """Only schedule experiments that have not already completed."""
    status_path = exp_dir / "status.yml"
    if not status_path.exists():
        return False

    try:
        status_data = _load_yaml(status_path)
    except (OSError, yaml.YAMLError):
        return False

    return status_data.get("status", "ready") in {"ready", "failed"}


def discover_experiment_jobs(
    hypothesis_dir: Path,
    max_experiments: int,
) -> list[ExperimentJob]:
    """Find backend-created experiment skeletons and assign distinct variations."""
    experiments_dir = hypothesis_dir / "experiments"

    if not experiments_dir.exists():
        raise FileNotFoundError(
            f"Backend-created experiments directory not found: {experiments_dir}"
        )

    candidates: list[tuple[Path, Path]] = []

    for exp_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
        experiment_yml = _experiment_yml_path(exp_dir)
        if experiment_yml is not None and _is_runnable(exp_dir):
            candidates.append((exp_dir, experiment_yml))

    if len(candidates) < max_experiments:
        raise RuntimeError(
            "Not enough backend-created experiment skeletons: "
            f"required={max_experiments}, runnable={len(candidates)}"
        )

    jobs: list[ExperimentJob] = []

    for offset, (exp_dir, experiment_yml) in enumerate(candidates[:max_experiments]):
        profile = VARIATION_PROFILES[offset % len(VARIATION_PROFILES)]
        cycle = offset // len(VARIATION_PROFILES) + 1

        jobs.append(
            ExperimentJob(
                exp_id=exp_dir.name,
                exp_dir=exp_dir,
                experiment_yml=experiment_yml,
                index=offset + 1,
                total=max_experiments,
                variation_instruction=f"{profile} Variation cycle: {cycle}.",
            )
        )

    return jobs


def _format_event(event: dict) -> Iterable[str]:
    """Convert LangGraph stream events into short per-experiment log lines."""
    for node_name, value in event.items():
        messages = value.get("messages") if isinstance(value, dict) else None

        if not messages:
            yield f"[{node_name}] {value}"
            continue

        message = messages[-1]
        reasoning = message.additional_kwargs.get("reasoning_content", "")

        if reasoning:
            yield f"[{node_name}] reasoning: {reasoning[:300]}"

        if message.content:
            yield f"[{node_name}] {str(message.content)[:500]}"


def _write_log(log_file: Path, line: str) -> None:
    """Append one line to an experiment log and mirror it to stdout safely."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")

    with PRINT_LOCK:
        print(line, flush=True)


def _read_status(exp_dir: Path) -> str | None:
    """Return the current experiment status, if the status file is readable."""
    try:
        return _load_yaml(exp_dir / "status.yml").get("status")
    except (OSError, yaml.YAMLError):
        return None


def _read_experiment_formula(experiment_yml: Path) -> str:
    """Read the required evaluation formula from experiment YAML."""
    experiment = _load_yaml(experiment_yml)
    evaluation_formula = (experiment.get("design") or {}).get("formula")

    if not evaluation_formula:
        raise ValueError(f"Experiment formula is missing: {experiment_yml}")

    return str(evaluation_formula)


def _design_errors(job: ExperimentJob, expected_formula: str) -> list[str]:
    """Validate that the design phase filled the required YAML fields."""
    errors: list[str] = []

    try:
        experiment = _load_yaml(job.experiment_yml)
    except (OSError, yaml.YAMLError):
        return ["experiment YAML is unreadable"]

    if experiment.get("exp_id") not in {None, job.exp_id}:
        errors.append("exp_id was changed")

    design = experiment.get("design") or {}

    for field in ("experiment_text", "model", "features"):
        if design.get(field) in (None, "", [], {}):
            errors.append(f"design.{field} is empty")

    if not isinstance(design.get("hyperparameters"), dict):
        errors.append("design.hyperparameters must be a mapping")

    if design.get("formula") != expected_formula:
        errors.append("design.formula was changed")

    return errors


def _mark_failed(exp_dir: Path, message: str) -> None:
    update_status.invoke(
        {
            "exp_dir": str(exp_dir),
            "current_task": "실험 실패",
            "status": "failed",
            "analysis_text": message[:1000],
        }
    )


def mark_screening_rejection(
    hypothesis_dir: Path,
    result: ScreeningResult,
) -> None:
    """Expose a rejected preflight decision through every experiment status file."""
    experiments_dir = hypothesis_dir / "experiments"
    if not experiments_dir.exists():
        return

    message = f"[{result.category}] {result.reason}"
    for exp_dir in experiments_dir.iterdir():
        if not exp_dir.is_dir() or not (exp_dir / "status.yml").exists():
            continue
        update_status.invoke(
            {
                "exp_dir": str(exp_dir),
                "current_task": "요청 필터링됨",
                "status": "failed",
                "analysis_text": message,
            }
        )


def run_experiment(
    job: ExperimentJob,
    *,
    project_id: str,
    u_id: str,
    hypothesis_id: str,
    hypothesis_dir: Path,
    graph_factory: Callable,
    phase_name: str = "execution",
    require_done: bool = True,
) -> str:
    """Run one experiment graph and isolate its logs and failure status.

    require_done=False is used for design-only graphs because the design phase
    should not set status=done.
    """
    log_file = job.exp_dir / "agent.log"
    prefix = f"[{job.exp_id} {job.index}/{job.total} {phase_name}]"

    _write_log(log_file, f"{prefix} starting: {job.variation_instruction}")

    update_status.invoke(
        {
            "exp_dir": str(job.exp_dir),
            "current_task": "실험 설계 중" if phase_name == "design" else "실험 실행 중",
            "status": "running",
        }
    )

    try:
        evaluation_formula = _read_experiment_formula(job.experiment_yml)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        _mark_failed(job.exp_dir, str(exc))
        _write_log(log_file, f"{prefix} failed: {exc}")
        return "failed"

    state = {
        "messages": [
            HumanMessage(
                content=(
                    "Start the assigned experiment workflow. Use tools properly, "
                    "make exactly one tool call at a time, and do not claim "
                    "completion until required artifacts physically exist."
                )
            )
        ],
        "project_id": project_id,
        "u_id": u_id,
        "hypothesis_id": hypothesis_id,
        "hypothesis_dir": str(hypothesis_dir),
        "exp_id": job.exp_id,
        "exp_dir": str(job.exp_dir),
        "experiment_yml": str(job.experiment_yml),
        "experiment_index": job.index,
        "experiment_total": job.total,
        "variation_instruction": job.variation_instruction,
        "evaluation_formula": evaluation_formula,
        "stage": phase_name,
        "stage_attempts": {},
        "stage_tool_calls": {},
        "no_tool_attempts": 0,
        "design_retry_attempts": 0,
        "stage_result": "next",
    }

    try:
        graph = graph_factory()

        for event in graph.stream(state, {"recursion_limit": 200}):
            for line in _format_event(event):
                _write_log(log_file, f"{prefix} {line}")

    except Exception as exc:
        _mark_failed(job.exp_dir, str(exc))
        _write_log(log_file, f"{prefix} failed: {exc}")
        return "failed"

    final_status = _read_status(job.exp_dir)

    if final_status == "failed":
        _write_log(log_file, f"{prefix} failed: graph recorded a terminal failure")
        return "failed"

    if phase_name == "design":
        errors = _design_errors(job, expected_formula=evaluation_formula)
        if errors:
            message = "Design phase finished with invalid design: " + "; ".join(errors)
            _mark_failed(job.exp_dir, message)
            _write_log(log_file, f"{prefix} failed: {message}")
            return "failed"

    if require_done and final_status != "done":
        message = "Agent graph finished without setting status.yml to done"
        _mark_failed(job.exp_dir, message)
        _write_log(log_file, f"{prefix} failed: {message}")
        return "failed"

    _write_log(log_file, f"{prefix} completed")
    return "done"


def run_parallel_experiments(
    jobs: list[ExperimentJob],
    *,
    parallel_count: int,
    project_id: str,
    u_id: str,
    hypothesis_id: str,
    hypothesis_dir: Path,
    graph_factory: Callable,
    phase_name: str = "execution",
    require_done: bool = True,
) -> dict[str, str]:
    """Run all jobs with at most parallel_count active experiments."""
    results: dict[str, str] = {}

    if not jobs:
        return results

    with ThreadPoolExecutor(
        max_workers=min(parallel_count, len(jobs)),
        thread_name_prefix=f"hypoloop-{phase_name}",
    ) as executor:
        futures = {
            executor.submit(
                run_experiment,
                job,
                project_id=project_id,
                u_id=u_id,
                hypothesis_id=hypothesis_id,
                hypothesis_dir=hypothesis_dir,
                graph_factory=graph_factory,
                phase_name=phase_name,
                require_done=require_done,
            ): job
            for job in jobs
        }

        for future in as_completed(futures):
            job = futures[future]

            try:
                results[job.exp_id] = future.result()
            except Exception as exc:
                message = f"Unhandled worker exception: {exc}"
                _mark_failed(job.exp_dir, message)
                _write_log(job.exp_dir / "agent.log", f"[{job.exp_id}] failed: {message}")
                results[job.exp_id] = "failed"

    return results


def main() -> int:
    """Load one hypothesis and execute its backend-created experiments in two phases."""
    parser = argparse.ArgumentParser(description="Hypo Loop Agent Runner")
    parser.add_argument("--trigger_id", default="1", help="트리거 고유 ID")
    parser.add_argument("--project_id", required=True, help="대상 프로젝트 ID")
    parser.add_argument("--hypothesis_id", required=True, help="대상 가설 ID")
    parser.add_argument("--u_id", default="demo_user", help="사용자 ID")
    args = parser.parse_args()

    hypothesis_dir = (
        PROJECT_ROOT
        / "data"
        / "projects"
        / args.project_id
        / "hypotheses"
        / args.hypothesis_id
    )
    hypothesis_file = hypothesis_dir / f"{args.u_id}_{args.hypothesis_id}.yml"

    try:
        hypothesis = load_hypothesis(hypothesis_file)

        screening = screen_hypothesis(str(hypothesis["content"]))
        if not screening.allowed:
            mark_screening_rejection(hypothesis_dir, screening)
            print(
                f"[!] Hypothesis rejected before design: "
                f"category={screening.category}, reason={screening.reason}"
            )
            return 1

        print("[*] Hypothesis passed safety, privacy, and ML relevance screening.")

        jobs = discover_experiment_jobs(
            hypothesis_dir,
            hypothesis["max_experiments"],
        )

        print(
            f"[*] Trigger {args.trigger_id}: design phase for {len(jobs)} experiments "
            f"with parallel_count={hypothesis['parallel_count']}"
        )

        design_results = run_parallel_experiments(
            jobs,
            parallel_count=hypothesis["parallel_count"],
            project_id=args.project_id,
            u_id=args.u_id,
            hypothesis_id=args.hypothesis_id,
            hypothesis_dir=hypothesis_dir,
            graph_factory=build_design_graph,
            phase_name="design",
            require_done=False,
        )

        designed_jobs = [
            job for job in jobs
            if design_results.get(job.exp_id) == "done"
        ]

        design_failed = len(jobs) - len(designed_jobs)

        print(
            f"[*] Design phase completed: "
            f"done={len(designed_jobs)}, failed={design_failed}"
        )

        if not designed_jobs:
            print("[!] No experiments passed the design phase.")
            return 1

        print(
            f"[*] Trigger {args.trigger_id}: execution phase for {len(designed_jobs)} "
            f"experiments with parallel_count={hypothesis['parallel_count']}"
        )

        execution_results = run_parallel_experiments(
            designed_jobs,
            parallel_count=hypothesis["parallel_count"],
            project_id=args.project_id,
            u_id=args.u_id,
            hypothesis_id=args.hypothesis_id,
            hypothesis_dir=hypothesis_dir,
            graph_factory=build_execution_graph,
            phase_name="execution",
            require_done=True,
        )

    except Exception as exc:
        print(f"[!] Agent runner failed before scheduling: {exc}")
        return 1

    execution_failed = sum(status == "failed" for status in execution_results.values())
    execution_done = len(execution_results) - execution_failed
    total_failed = design_failed + execution_failed

    print(
        f"[*] Agent runner completed: "
        f"design_done={len(designed_jobs)}, "
        f"execution_done={execution_done}, "
        f"failed={total_failed}"
    )

    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
