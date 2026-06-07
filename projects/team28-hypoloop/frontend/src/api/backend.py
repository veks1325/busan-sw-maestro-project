"""BackendStore — 실제 FastAPI 백엔드와 통신하는 HypoStore 구현체.

핵심은 '통신'이다: 프로젝트/가설 CRUD, 트리거(ready), 리포트 조회는 모두
실제 백엔드 API를 호출한다. 에이전트가 아직 없어 실시간 단계 이벤트를
보낼 수 없는 run()만 더미 진행 표시로 채우고, 완료 여부는 실제 리포트를
폴링해 판단한다(에이전트가 붙으면 동일한 흐름으로 자연스럽게 동작한다).
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Dict, Iterator, List, Optional, Tuple

import requests

from src.api.types import AgentEvent, Hypothesis, Project

_DEFAULT_BASE_URL = "http://localhost:8000"
_POLL_INTERVAL = 1.5
_MAX_POLLS = 400  # 폴링 안전 상한(약 10분) — 에이전트 미동작 시 무한 대기 방지


class BackendStore:
    """HypoStore 구현(실제 백엔드 연동). 세션 동안 메모리 캐시를 함께 사용한다."""

    def __init__(self, base_url: Optional[str] = None, u_id: str = "demo_user") -> None:
        self._base_url = (base_url or os.getenv("HYPOLOOP_BACKEND_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._u_id = u_id
        self._session = requests.Session()
        self._name_overrides: Dict[str, str] = {}
        self._hyps: Dict[str, Hypothesis] = {}
        self._threads: Dict[str, threading.Thread] = {}

    # ------------------------------------------------------------------
    # HTTP 헬퍼
    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _get(self, path: str, **kwargs) -> object:
        r = self._session.get(self._url(path), timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, **kwargs) -> object:
        r = self._session.post(self._url(path), timeout=30, **kwargs)
        r.raise_for_status()
        if not r.content:
            return None
        return r.json()

    def _delete(self, path: str, **kwargs) -> None:
        r = self._session.delete(self._url(path), timeout=30, **kwargs)
        r.raise_for_status()

    # ------------------------------------------------------------------
    # 프로젝트
    # ------------------------------------------------------------------
    def list_projects(self) -> List[Project]:
        items = self._get("/projects")
        projects = [
            Project(project_id=d["project_id"],
                    name=self._name_overrides.get(d["project_id"], d["name"]))
            for d in items
        ]
        if not projects:
            # 데모 편의를 위해 최초 1개를 자동 생성한다(이름은 고정값).
            projects = [self.create_project("Hypo Loop 프로젝트")]
        return projects

    def create_project(self, name: str) -> Project:
        data = self._post("/projects", json={"name": name})
        project_id = data["project_id"]
        self._name_overrides[project_id] = name
        return Project(project_id=project_id, name=name)

    def rename_project(self, project_id: str, name: str) -> Project:
        # 프로젝트 이름은 데이터 계층에 저장하지 않는 고정 항목 — 화면 표시만 갱신한다.
        self._name_overrides[project_id] = name
        return Project(project_id=project_id, name=name)

    def delete_project(self, project_id: str) -> None:
        self._delete(f"/projects/{project_id}")
        self._name_overrides.pop(project_id, None)
        for hid in [h.hypothesis_id for h in self._hyps.values() if h.project_id == project_id]:
            self._hyps.pop(hid, None)

    # ------------------------------------------------------------------
    # 가설
    # ------------------------------------------------------------------
    def list_hypotheses(self, project_id: str) -> List[Hypothesis]:
        items = self._get(f"/projects/{project_id}/hypotheses")
        out = []
        for d in items:
            h = self._hyps.get(d["hypothesis_id"])
            if h is None:
                h = Hypothesis(
                    hypothesis_id=d["hypothesis_id"], project_id=project_id,
                    content=d["content"], max_experiments=d["max_experiments"],
                    parallel_count=d["parallel_count"],
                )
                self._hyps[h.hypothesis_id] = h
            # 실행 스레드가 진행 중이 아니면 백엔드가 계산한 상태/점수로 동기화한다.
            thread = self._threads.get(h.hypothesis_id)
            if thread is None or not thread.is_alive():
                h.status = d["status"]
                h.best_score = d["best_score"]
            out.append(h)
        return out

    def create_hypothesis(self, project_id: str, content: str,
                          max_experiments: int, parallel_count: int) -> Hypothesis:
        data = self._post(
            f"/projects/{project_id}/hypotheses",
            json={"u_id": self._u_id, "content": content,
                  "max_experiments": max_experiments, "parallel_count": parallel_count},
        )
        h = Hypothesis(hypothesis_id=data["hypothesis_id"], project_id=project_id,
                       content=content, max_experiments=max_experiments,
                       parallel_count=parallel_count)
        self._hyps[h.hypothesis_id] = h
        return h

    def delete_hypothesis(self, hypothesis_id: str) -> None:
        h = self._hyps.get(hypothesis_id)
        project_id = h.project_id if h is not None else self._find_project_id(hypothesis_id)
        self._delete(f"/hypotheses/{hypothesis_id}", params={"project_id": project_id})
        self._hyps.pop(hypothesis_id, None)

    def _find_project_id(self, hypothesis_id: str) -> str:
        """캐시에 없는 가설의 project_id를 찾는다(직접 진입 등 드문 경로 대비)."""
        for p in self.list_projects():
            for d in self._get(f"/projects/{p.project_id}/hypotheses"):
                if d["hypothesis_id"] == hypothesis_id:
                    return p.project_id
        raise KeyError(hypothesis_id)

    # ------------------------------------------------------------------
    # 실행 — 에이전트가 아직 없으므로 트리거 후 더미 진행을 보여주고
    # 완료 여부만 실제 리포트를 폴링해 판단한다.
    # ------------------------------------------------------------------
    def start_run(self, hypothesis_id: str) -> None:
        h = self._hyps[hypothesis_id]
        h.status = "running"
        h.score_history = []
        h.events = []
        prev = self._threads.get(hypothesis_id)
        if prev is not None and prev.is_alive():
            return
        t = threading.Thread(target=self._drain, args=(hypothesis_id,), daemon=True)
        self._threads[hypothesis_id] = t
        t.start()

    def _drain(self, hypothesis_id: str) -> None:
        try:
            for ev in self.run(hypothesis_id):
                h = self._hyps.get(hypothesis_id)
                if h is None:
                    return
                h.events.append(ev)
        except KeyError:
            return

    def run(self, hypothesis_id: str) -> Iterator[AgentEvent]:
        h = self._hyps[hypothesis_id]
        h.status = "running"
        h.score_history = []

        self._post(f"/hypotheses/{hypothesis_id}/ready",
                   params={"project_id": h.project_id, "u_id": self._u_id})
        yield AgentEvent("트리거", "step", "백엔드가 가설 yml을 ready로 표시하고 에이전트를 호출했습니다")
        yield AgentEvent("대기", "log", "에이전트가 실험을 진행하면 점수/보고서가 자동으로 채워집니다 (현재는 폴링 대기 중)")

        seen_scores = 0
        last_seen_task = None
        for _ in range(_MAX_POLLS):
            time.sleep(_POLL_INTERVAL)
            try:
                report = self._get(f"/hypotheses/{hypothesis_id}/report",
                                   params={"project_id": h.project_id})
            except requests.RequestException:
                continue

            history = report.get("score_history", [])
            if history:
                latest_task = history[-1].get("current_task")
                if latest_task and latest_task != last_seen_task:
                    yield AgentEvent("진행 중", "step", f"에이전트가 {latest_task}를 수행중입니다")
                    last_seen_task = latest_task

            scores = [e["score"] for e in history if e.get("score") is not None]
            while seen_scores < len(scores):
                score = scores[seen_scores]
                seen_scores += 1
                h.score_history.append(score)
                yield AgentEvent("학습/평가", "metric", f"실험 점수 {score}", score=score)

            statuses = [e.get("status") for e in history]
            if any(s == "failed" for s in statuses):
                h.status = "error"
                yield AgentEvent("오류", "log", "실험이 실패 상태로 종료되었습니다")
                return
            if statuses and len(statuses) >= h.max_experiments and all(s == "done" for s in statuses):
                break
        else:
            yield AgentEvent("시간 초과", "log", "대기 시간 내에 실험이 완료되지 않았습니다")
            return

        report = self._get(f"/hypotheses/{hypothesis_id}/report",
                           params={"project_id": h.project_id})
        h.best_score = report.get("best_score")
        texts = [t["text"] for t in report.get("analysis_texts", []) if t.get("text")]
        h.analysis_text = "\n".join(texts)
        h.report_md = self._build_report_md(h, report)
        h.status = "done"
        yield AgentEvent("보고서 작성", "log", "보고서 작성 완료")

    def _build_report_md(self, h: Hypothesis, report: dict) -> str:
        """백엔드 리포트 데이터를 사람이 읽을 수 있는 마크다운으로 정리한다(간단 버전)."""
        scores = h.score_history
        rows = "\n".join(f"| {i} | {s} |" for i, s in enumerate(scores, start=1)) or "| - | - |"
        best_line = f"- 최고 점수: **{h.best_score}**" if h.best_score is not None else "- 점수 데이터 없음"
        return (
            f"# 분석 보고서\n\n"
            f"## 가설\n\n> {h.content}\n\n"
            f"## 실험 설정\n\n"
            f"- 최대 실험 횟수: {h.max_experiments}\n"
            f"- 병렬 횟수: {h.parallel_count}\n\n"
            f"## 실험별 점수\n\n| 실험 | 점수 |\n| --- | --- |\n{rows}\n\n"
            f"## 성능 요약\n\n{best_line}\n\n"
            f"## 분석\n\n{h.analysis_text or '에이전트가 작성한 분석 텍스트가 없습니다.'}\n"
        )

    # ------------------------------------------------------------------
    # 보고서 / 집계
    # ------------------------------------------------------------------
    def get_report(self, hypothesis_id: str) -> Hypothesis:
        h = self._hyps.get(hypothesis_id)
        if h is None:
            project_id = self._find_project_id(hypothesis_id)
            for d in self._get(f"/projects/{project_id}/hypotheses"):
                if d["hypothesis_id"] == hypothesis_id:
                    h = Hypothesis(hypothesis_id=hypothesis_id, project_id=project_id,
                                   content=d["content"], max_experiments=d["max_experiments"],
                                   parallel_count=d["parallel_count"], status=d["status"],
                                   best_score=d["best_score"])
                    self._hyps[hypothesis_id] = h
                    break
        if h is None:
            raise KeyError(hypothesis_id)

        if h.status == "done" and not h.report_md:
            report = self._get(f"/hypotheses/{hypothesis_id}/report",
                               params={"project_id": h.project_id})
            h.best_score = report.get("best_score")
            h.score_history = [e["score"] for e in report.get("score_history", [])
                               if e.get("score") is not None]
            texts = [t["text"] for t in report.get("analysis_texts", []) if t.get("text")]
            h.analysis_text = "\n".join(texts)
            h.report_md = self._build_report_md(h, report)
        return h

    def best_scores(self, project_id: str) -> List[Tuple[Hypothesis, float]]:
        return [(h, h.best_score) for h in self.list_hypotheses(project_id)
                if h.status == "done" and h.best_score is not None]
