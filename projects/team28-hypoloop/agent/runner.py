import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import yaml
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agent.src.graph.main_graph import build_graph
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
    with status_path.open("r", encoding="utf-8") as file:
        status_data = yaml.safe_load(file) or {}
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

    jobs = []
    for offset, (exp_dir, experiment_yml) in enumerate(
        candidates[:max_experiments]
    ):
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
    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"{line}\n")
    with PRINT_LOCK:
        print(line, flush=True)


def _read_status(exp_dir: Path) -> str | None:
    """Return the current experiment status, if the status file is readable."""
    try:
        with (exp_dir / "status.yml").open("r", encoding="utf-8") as file:
            return (yaml.safe_load(file) or {}).get("status")
    except (OSError, yaml.YAMLError):
        return None


def run_experiment(
    job: ExperimentJob,
    *,
    project_id: str,
    u_id: str,
    hypothesis_id: str,
    hypothesis_dir: Path,
    graph_factory: Callable = build_graph,
) -> str:
    """Run one experiment graph and isolate its logs and failure status."""
    log_file = job.exp_dir / "agent.log"
    prefix = f"[{job.exp_id} {job.index}/{job.total}]"
    _write_log(log_file, f"{prefix} starting: {job.variation_instruction}")
    update_status.invoke(
        {
            "exp_dir": str(job.exp_dir),
            "current_task": "실험 시작",
            "status": "running",
        }
    )

    try:
        with job.experiment_yml.open("r", encoding="utf-8") as file:
            experiment = yaml.safe_load(file) or {}
        evaluation_formula = (experiment.get("design") or {}).get("formula")
        if not evaluation_formula:
            raise ValueError(f"Experiment formula is missing: {job.experiment_yml}")
    except (OSError, yaml.YAMLError, ValueError) as exc:
        update_status.invoke(
            {
                "exp_dir": str(job.exp_dir),
                "current_task": "실험 실패",
                "status": "failed",
                "analysis_text": str(exc)[:1000],
            }
        )
        _write_log(log_file, f"{prefix} failed: {exc}")
        return "failed"

    state = {
        "messages": [
            HumanMessage(
                content=(
                    "Start the staged experiment workflow. Work only on the current "
                    "stage and use tools until that stage's artifacts are complete."
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
        "evaluation_formula": str(evaluation_formula),
        "stage": "design",
        "stage_attempts": {},
        "stage_tool_calls": {},
        "stage_result": "next",
    }

    try:
        graph = graph_factory()
        for event in graph.stream(state, {"recursion_limit": 200}):
            for line in _format_event(event):
                _write_log(log_file, f"{prefix} {line}")
    except Exception as exc:
        update_status.invoke(
            {
                "exp_dir": str(job.exp_dir),
                "current_task": "실험 실패",
                "status": "failed",
                "analysis_text": str(exc)[:1000],
            }
        )
        _write_log(log_file, f"{prefix} failed: {exc}")
        return "failed"

    final_status = _read_status(job.exp_dir)
    if final_status == "failed":
        _write_log(log_file, f"{prefix} failed: graph recorded a terminal stage failure")
        return "failed"
    if final_status != "done":
        message = "Agent graph finished without setting status.yml to done"
        update_status.invoke(
            {
                "exp_dir": str(job.exp_dir),
                "current_task": "실험 실패",
                "status": "failed",
                "analysis_text": message,
            }
        )
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
    graph_factory: Callable = build_graph,
) -> dict[str, str]:
    """Run all jobs with at most parallel_count active experiments."""
    results: dict[str, str] = {}
    with ThreadPoolExecutor(
        max_workers=min(parallel_count, len(jobs)),
        thread_name_prefix="hypoloop-exp",
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
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            results[job.exp_id] = future.result()
    return results


def main() -> int:
    """Load one hypothesis and execute its backend-created experiments in parallel."""
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
        jobs = discover_experiment_jobs(
            hypothesis_dir,
            hypothesis["max_experiments"],
        )
        print(
            f"[*] Trigger {args.trigger_id}: scheduling {len(jobs)} experiments "
            f"with parallel_count={hypothesis['parallel_count']}"
        )
        results = run_parallel_experiments(
            jobs,
            parallel_count=hypothesis["parallel_count"],
            project_id=args.project_id,
            u_id=args.u_id,
            hypothesis_id=args.hypothesis_id,
            hypothesis_dir=hypothesis_dir,
        )
    except Exception as exc:
        print(f"[!] Agent runner failed before scheduling: {exc}")
        return 1

    failed = sum(status == "failed" for status in results.values())
    print(f"[*] Agent runner completed: done={len(results) - failed}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
