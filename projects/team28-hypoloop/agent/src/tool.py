import os
import re
import subprocess
from pathlib import Path

from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "mlruns",
}

MAX_DEPTH = 5
MAX_ENTRIES = 200
MAX_MATCHES = 100


def _resolve_safe(path: str) -> Path:
    """LLM이 준 path를 PROJECT_ROOT 기준으로 resolve하고 루트 밖이면 거부."""
    target = (PROJECT_ROOT / path).resolve()
    # Path.is_relative_to 는 3.9+; requires-python >=3.10 이라 안전
    if not target.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"경로가 프로젝트 루트를 벗어났습니다: {path}")
    return target


@tool
def list_directory(path: str) -> str:
    """프로젝트 폴더 트리 구조 및 파일 목록 확인 (ls, tree 역할)"""
    try:
        target = _resolve_safe(path)
    except ValueError as e:
        return str(e)

    if not target.exists():
        return f"경로를 찾을 수 없습니다: {path}"
    if not target.is_dir():
        return f"디렉터리가 아닙니다: {path}"

    lines: list[str] = []
    truncated = False

    for dirpath, dirnames, filenames in os.walk(target):
        current = Path(dirpath)
        depth = len(current.relative_to(target).parts)

        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)  # in-place 수정으로 하위 순회까지 차단

        if depth >= MAX_DEPTH:
            dirnames[:] = []
            continue

        indent = "  " * depth
        if depth == 0:
            lines.append(f"{path.rstrip('/')}/")
        else:
            lines.append(f"{indent}{current.name}/")

        if len(lines) >= MAX_ENTRIES:
            truncated = True
            break

        for name in sorted(filenames):
            lines.append(f"{indent}  {name}")
            if len(lines) >= MAX_ENTRIES:
                truncated = True
                break

        if truncated:
            break

    if not lines:
        return f"비어 있는 디렉터리입니다: {path}"
    if truncated:
        lines.append("... (항목이 더 있습니다)")
    return "\n".join(lines)


@tool
def search_code(pattern: str, path: str) -> str:
    """특정 변수나 함수가 사용된 위치 검색 (grep 역할)"""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"잘못된 정규식 패턴입니다: {pattern} ({e})"

    try:
        target = _resolve_safe(path)
    except ValueError as e:
        return str(e)

    if not target.exists():
        return f"경로를 찾을 수 없습니다: {path}"

    files: list[Path] = []
    if target.is_file():
        files.append(target)
    else:
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for name in filenames:
                files.append(Path(dirpath) / name)

    results: list[str] = []
    truncated = False
    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        rel = file.relative_to(PROJECT_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append(f"{rel}:{lineno}: {line.strip()}")
                if len(results) >= MAX_MATCHES:
                    truncated = True
                    break
        if truncated:
            break

    if not results:
        return "일치하는 결과가 없습니다."
    if truncated:
        results.append("... (결과가 더 있습니다)")
    return "\n".join(results)


@tool
def read_file(file_path: str) -> str:
    """소스 코드 내용 확인"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


@tool
def write_file(file_path: str, content: str) -> str:
    """에이전트가 생각한 ML 코드를 실제 파이썬 파일로 저장"""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file {file_path}: {str(e)}"


@tool
def execute_command(command: str) -> str:
    """터미널에서 스크립트를 구동하고, 결과(Stdout) 및 에러(Stderr) 반환"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )

        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            output += f"Stdout:\n{result.stdout}\n"
        if result.stderr:
            output += f"Stderr:\n{result.stderr}\n"

        return output
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def update_status(exp_dir: str, current_task: str, status: str, analysis_text: str = None, score: float = None) -> str:
    """프론트엔드 UI에 진행 상황을 실시간으로 알리기 위해 status.yml을 업데이트합니다.
    status는 'ready', 'running', 'done', 'failed' 중 하나여야 합니다.
    작업 단계가 바뀔 때마다(예: EDA 시작, 모델 학습 시작, 완료 등) 이 도구를 호출하세요.
    실험이 완료되어 평가 점수(예: R2 Score)가 나왔다면 score 파라미터도 함께 전달하세요."""
    import yaml
    from datetime import datetime
    
    status_path = os.path.join(exp_dir, "status.yml")
    
    try:
        data = {}
        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                pass
                
        data["current_task"] = current_task
        data["status"] = status
        data["last_updated"] = datetime.now().isoformat()
        if analysis_text is not None:
            data["analysis_text"] = analysis_text
            
        with open(status_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
            
        # If score is provided, also update {exp_id}.yml
        if score is not None:
            exp_id = os.path.basename(os.path.normpath(exp_dir))
            exp_yml_path = os.path.join(exp_dir, f"{exp_id}.yml")
            
            exp_data = {}
            if os.path.exists(exp_yml_path):
                try:
                    with open(exp_yml_path, "r", encoding="utf-8") as f:
                        exp_data = yaml.safe_load(f) or {}
                except Exception:
                    pass
            exp_data["score"] = float(score)
            with open(exp_yml_path, "w", encoding="utf-8") as f:
                yaml.dump(exp_data, f, allow_unicode=True)
            
        return f"Status successfully updated to: {status} ({current_task})"
    except Exception as e:
        return f"Error updating status: {str(e)}"


tools = [
    list_directory,
    search_code,
    read_file,
    write_file,
    execute_command,
    update_status
]
