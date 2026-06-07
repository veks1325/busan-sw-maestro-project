# HTTP API 엔드포인트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프론트↔백엔드를 HTTP API로 분리한다 — 참조 FastAPI 서버(잡 스토어+폴링) + 기존 `PipelineBackend` 계약을 구현하는 `ApiBackend` 클라이언트로, 대시보드 코드 변경 없이 백엔드를 별도 프로세스로 띄운다.

**Architecture:** 비동기 잡 모델. POST /jobs가 백그라운드 스레드로 파이프라인을 실행하고 이벤트를 인메모리 잡 스토어에 적재. 프론트의 `ApiBackend`는 POST 후 GET /events?after=N을 폴링하며 `ProgressEvent`를 yield, 완료 시 GET /result. 직렬화는 `api/schema.py` 단일 출처.

**Tech Stack:** Python 3.10, FastAPI, uvicorn, httpx, Streamlit, pandas, pytest

참고 스펙: `docs/superpowers/specs/2026-06-05-http-api-endpoint-design.md`
작업 위치: `/Users/justice/Desktop/AI 교육` (루트 레이아웃)

---

## 파일 구조

```
api/__init__.py          # 빈 패키지
api/schema.py            # dataclass ↔ dict 직렬화 (와이어 포맷 단일 출처)
api/job_store.py         # 인메모리 잡 스토어 + 백그라운드 스레드 실행 (backend 팩토리 주입)
api/server.py            # FastAPI 앱 + 엔드포인트 (create_app(backend_factory))
backend/api_backend.py   # ApiBackend(PipelineBackend): httpx HTTP 클라이언트
app.py                   # get_backend(): HYPOLOOP_API_URL 있으면 ApiBackend, 없으면 MockBackend
requirements.txt         # fastapi, uvicorn[standard], httpx 추가
tests/test_api_schema.py
tests/test_api_job_store.py
tests/test_api_server.py
tests/test_api_backend.py
tests/test_app_backend_selection.py
```

---

## Task 1: 의존성 + schema 직렬화

**Files:**
- Modify: `requirements.txt`
- Create: `api/__init__.py`, `api/schema.py`
- Test: `tests/test_api_schema.py`

- [ ] **Step 1: 의존성 추가** — `requirements.txt`에 세 줄 추가(기존 내용 유지):
```
fastapi>=0.110
uvicorn[standard]>=0.29
httpx>=0.27
```

- [ ] **Step 2: 설치**

Run: `pip install -r requirements.txt`
Expected: fastapi/uvicorn/httpx 설치 성공.

- [ ] **Step 3: 빈 패키지 생성**

Run: `mkdir -p api && : > api/__init__.py`

- [ ] **Step 4: 실패 테스트 작성** — `tests/test_api_schema.py`:
```python
from backend.interface import (
    DataCard, PipelineInput, ProgressEvent, MetricRecord, PipelineResult,
)
from api import schema


def test_metric_roundtrip():
    m = MetricRecord(1, "accuracy", 0.7, 0.82)
    assert schema.metric_from_dict(schema.metric_to_dict(m)) == m


def test_metric_none():
    assert schema.metric_to_dict(None) is None
    assert schema.metric_from_dict(None) is None


def test_input_roundtrip():
    inp = PipelineInput("a.csv", 3, DataCard("y", "classification", "d"), "가설")
    assert schema.input_from_dict(schema.input_to_dict(inp)) == inp


def test_event_roundtrip_with_metric():
    m = MetricRecord(0, "accuracy", 0.7, 0.7)
    ev = ProgressEvent("베이스라인", 0, "running", "m", kind="metric", metric=m)
    assert schema.event_from_dict(schema.event_to_dict(ev)) == ev


def test_event_roundtrip_plain():
    ev = ProgressEvent("EDA", 0, "done", "done")
    out = schema.event_from_dict(schema.event_to_dict(ev))
    assert out == ev and out.kind == "stage" and out.metric is None


def test_result_roundtrip():
    r = PipelineResult("# r", "code", [MetricRecord(0, "accuracy", 0.7, 0.7)], "yaml")
    assert schema.result_from_dict(schema.result_to_dict(r)) == r
```

- [ ] **Step 5: 실패 확인**

Run: `python -m pytest tests/test_api_schema.py -v`
Expected: FAIL (ModuleNotFoundError: api.schema).

- [ ] **Step 6: 구현** — `api/schema.py`:
```python
"""dataclass ↔ dict(JSON) 직렬화 — HTTP 와이어 포맷의 단일 출처."""
from __future__ import annotations

from typing import List, Optional

from backend.interface import (
    DataCard, PipelineInput, ProgressEvent, MetricRecord, PipelineResult,
)


def metric_to_dict(m: Optional[MetricRecord]) -> Optional[dict]:
    if m is None:
        return None
    return {"loop_index": m.loop_index, "metric_name": m.metric_name,
            "baseline": m.baseline, "value": m.value}


def metric_from_dict(d: Optional[dict]) -> Optional[MetricRecord]:
    if d is None:
        return None
    return MetricRecord(loop_index=d["loop_index"], metric_name=d["metric_name"],
                        baseline=d["baseline"], value=d["value"])


def input_to_dict(inp: PipelineInput) -> dict:
    return {
        "csv_path": inp.csv_path,
        "loop_count": inp.loop_count,
        "data_card": {
            "target_column": inp.data_card.target_column,
            "task_type": inp.data_card.task_type,
            "description": inp.data_card.description,
        },
        "llm_instruction": inp.llm_instruction,
    }


def input_from_dict(d: dict) -> PipelineInput:
    dc = d["data_card"]
    return PipelineInput(
        csv_path=d["csv_path"],
        loop_count=d["loop_count"],
        data_card=DataCard(target_column=dc["target_column"],
                           task_type=dc["task_type"],
                           description=dc.get("description", "")),
        llm_instruction=d["llm_instruction"],
    )


def event_to_dict(ev: ProgressEvent) -> dict:
    return {"stage": ev.stage, "loop_index": ev.loop_index, "status": ev.status,
            "message": ev.message, "kind": ev.kind, "detail": ev.detail,
            "metric": metric_to_dict(ev.metric)}


def event_from_dict(d: dict) -> ProgressEvent:
    return ProgressEvent(stage=d["stage"], loop_index=d["loop_index"],
                         status=d["status"], message=d["message"],
                         kind=d.get("kind", "stage"), detail=d.get("detail", ""),
                         metric=metric_from_dict(d.get("metric")))


def result_to_dict(r: PipelineResult) -> dict:
    return {"report_md": r.report_md, "final_code": r.final_code,
            "metrics_history": [metric_to_dict(m) for m in r.metrics_history],
            "experiment_yaml": r.experiment_yaml}


def result_from_dict(d: dict) -> PipelineResult:
    return PipelineResult(
        report_md=d["report_md"], final_code=d["final_code"],
        metrics_history=[metric_from_dict(m) for m in d["metrics_history"]],
        experiment_yaml=d.get("experiment_yaml", ""))
```

- [ ] **Step 7: 통과 확인**

Run: `python -m pytest tests/test_api_schema.py -v`
Expected: PASS (6 passed).

- [ ] **Step 8: Commit**
```bash
git add requirements.txt api/__init__.py api/schema.py tests/test_api_schema.py
git commit -m "feat: API wire-format schema (dataclass <-> dict) + deps"
```

---

## Task 2: 잡 스토어 (백그라운드 실행)

**Files:**
- Create: `api/job_store.py`
- Test: `tests/test_api_job_store.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_api_job_store.py`:
```python
import time

from backend.mock import MockBackend
from backend.interface import DataCard, PipelineInput
from api.job_store import JobStore


def make_inp(loop_count=2):
    return PipelineInput("sample_data/sample.csv", loop_count,
                         DataCard("Survived", "classification", "t"), "가설")


def _wait_done(store, job_id, tries=300):
    for _ in range(tries):
        res = store.get_events(job_id, 0)
        if res["status"] in ("done", "failed"):
            return res
        time.sleep(0.01)
    return res


def test_job_completes_with_events_and_result():
    store = JobStore(lambda: MockBackend(step_delay=0.0))
    job_id = store.submit(make_inp())
    res = _wait_done(store, job_id)
    assert res["status"] == "done"
    assert len(res["events"]) > 0
    status, result = store.get_result(job_id)
    assert status == "ok"
    assert result["report_md"].startswith("#")


def test_get_events_incremental():
    store = JobStore(lambda: MockBackend(step_delay=0.0))
    job_id = store.submit(make_inp())
    _wait_done(store, job_id)
    first = store.get_events(job_id, 0)
    # next 인덱스 이후로는 새 이벤트 없음
    again = store.get_events(job_id, first["next"])
    assert again["events"] == []
    assert again["next"] == first["next"]


def test_unknown_job():
    store = JobStore(lambda: MockBackend())
    assert store.get_events("nope", 0) is None
    assert store.get_result("nope")[0] == "not_found"


def test_validate_delegates():
    store = JobStore(lambda: MockBackend())
    bad = PipelineInput("sample_data/sample.csv", 0,
                        DataCard("Survived", "classification", "t"), "가설")
    errors = store.validate(bad)
    assert any("루프" in e for e in errors)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_api_job_store.py -v`
Expected: FAIL (ModuleNotFoundError: api.job_store).

- [ ] **Step 3: 구현** — `api/job_store.py`:
```python
"""인메모리 잡 스토어 — 백그라운드 스레드로 파이프라인을 실행하고 이벤트를 적재."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from backend.interface import PipelineBackend, PipelineInput
from api import schema


@dataclass
class _Job:
    status: str = "running"               # "running" | "done" | "failed"
    events: List[dict] = field(default_factory=list)
    result: Optional[dict] = None
    error: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobStore:
    """backend_factory()로 잡마다 새 PipelineBackend를 만들어 실행(상태 격리)."""

    def __init__(self, backend_factory: Callable[[], PipelineBackend]) -> None:
        self._backend_factory = backend_factory
        self._jobs: Dict[str, _Job] = {}

    def validate(self, inp: PipelineInput) -> List[str]:
        return self._backend_factory().validate_input(inp)

    def submit(self, inp: PipelineInput) -> str:
        job_id = uuid.uuid4().hex
        job = _Job()
        self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job, inp), daemon=True).start()
        return job_id

    def _run(self, job: _Job, inp: PipelineInput) -> None:
        try:
            backend = self._backend_factory()
            for ev in backend.run(inp):
                with job.lock:
                    job.events.append(schema.event_to_dict(ev))
            result = backend.get_result()
            with job.lock:
                job.result = schema.result_to_dict(result)
                job.status = "done"
        except Exception as exc:  # noqa: BLE001 - 실패를 잡 상태로 전달
            with job.lock:
                job.status = "failed"
                job.error = str(exc)

    def get_events(self, job_id: str, after: int) -> Optional[dict]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        with job.lock:
            return {"status": job.status, "events": job.events[after:],
                    "next": len(job.events)}

    def get_result(self, job_id: str) -> Tuple[str, Optional[object]]:
        """('ok', result) | ('not_ready', None) | ('failed', error) | ('not_found', None)"""
        job = self._jobs.get(job_id)
        if job is None:
            return ("not_found", None)
        with job.lock:
            if job.status == "failed":
                return ("failed", job.error)
            if job.status != "done" or job.result is None:
                return ("not_ready", None)
            return ("ok", job.result)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_api_job_store.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**
```bash
git add api/job_store.py tests/test_api_job_store.py
git commit -m "feat: in-memory job store with background pipeline execution"
```

---

## Task 3: FastAPI 서버

**Files:**
- Create: `api/server.py`
- Test: `tests/test_api_server.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_api_server.py`:
```python
import time

from fastapi.testclient import TestClient

from api.server import create_app
from backend.mock import MockBackend

INPUT = {
    "csv_path": "sample_data/sample.csv", "loop_count": 2,
    "data_card": {"target_column": "Survived", "task_type": "classification",
                  "description": "t"},
    "llm_instruction": "가설",
}


def _client():
    return TestClient(create_app(backend_factory=lambda: MockBackend(step_delay=0.0)))


def test_health():
    assert _client().get("/health").json()["status"] == "ok"


def test_job_lifecycle():
    c = _client()
    r = c.post("/jobs", json=INPUT)
    assert r.status_code == 201
    jid = r.json()["job_id"]
    after, status = 0, "running"
    for _ in range(400):
        e = c.get(f"/jobs/{jid}/events", params={"after": after}).json()
        after, status = e["next"], e["status"]
        if status in ("done", "failed"):
            break
        time.sleep(0.01)
    assert status == "done"
    res = c.get(f"/jobs/{jid}/result")
    assert res.status_code == 200
    assert res.json()["report_md"].startswith("#")


def test_validate_endpoint_reports_missing_target():
    c = _client()
    bad = {**INPUT, "data_card": {**INPUT["data_card"], "target_column": "없는컬럼"}}
    errors = c.post("/validate", json=bad).json()["errors"]
    assert any("없는컬럼" in e for e in errors)


def test_create_job_validation_400():
    c = _client()
    r = c.post("/jobs", json={**INPUT, "loop_count": 0})
    assert r.status_code == 400
    assert any("루프" in e for e in r.json()["errors"])


def test_unknown_job_404():
    assert _client().get("/jobs/nope/events").status_code == 404
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_api_server.py -v`
Expected: FAIL (ModuleNotFoundError: api.server).

- [ ] **Step 3: 구현** — `api/server.py`:
```python
"""FastAPI 참조 서버 — 잡 제출/폴링/결과 엔드포인트."""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from backend.interface import PipelineBackend
from backend.mock import MockBackend
from api import schema
from api.job_store import JobStore


def create_app(backend_factory: Optional[Callable[[], PipelineBackend]] = None) -> FastAPI:
    if backend_factory is None:
        backend_factory = MockBackend
    store = JobStore(backend_factory)
    app = FastAPI(title="hypoloop API")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/validate")
    def validate(payload: dict):
        inp = schema.input_from_dict(payload)
        return {"errors": store.validate(inp)}

    @app.post("/jobs", status_code=201)
    def create_job(payload: dict):
        inp = schema.input_from_dict(payload)
        errors = store.validate(inp)
        if errors:
            return JSONResponse(status_code=400, content={"errors": errors})
        return {"job_id": store.submit(inp)}

    @app.get("/jobs/{job_id}/events")
    def get_events(job_id: str, after: int = 0):
        res = store.get_events(job_id, after)
        if res is None:
            raise HTTPException(status_code=404, detail="job not found")
        return res

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str):
        status, payload = store.get_result(job_id)
        if status == "not_found":
            raise HTTPException(status_code=404, detail="job not found")
        if status == "not_ready":
            raise HTTPException(status_code=409, detail="job not done")
        if status == "failed":
            return JSONResponse(status_code=500, content={"error": payload})
        return payload

    return app


app = create_app()
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_api_server.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**
```bash
git add api/server.py tests/test_api_server.py
git commit -m "feat: FastAPI reference server (jobs/events/result endpoints)"
```

---

## Task 4: ApiBackend HTTP 클라이언트

**Files:**
- Create: `backend/api_backend.py`
- Test: `tests/test_api_backend.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_api_backend.py`:
```python
import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from backend.mock import MockBackend
from backend.api_backend import ApiBackend
from backend.interface import DataCard, PipelineInput, PIPELINE_STAGES


def _backend():
    app = create_app(backend_factory=lambda: MockBackend(step_delay=0.0))
    client = TestClient(app)
    return ApiBackend("http://testserver", client=client, poll_interval=0.0)


def _inp(loop_count=2, target="Survived"):
    return PipelineInput("sample_data/sample.csv", loop_count,
                         DataCard(target, "classification", "t"), "가설")


def test_run_yields_events_all_stages():
    events = list(_backend().run(_inp()))
    seen = {e.stage for e in events}
    for s in PIPELINE_STAGES:
        assert s in seen
    kinds = {e.kind for e in events}
    assert "metric" in kinds and "llm" in kinds


def test_get_result_after_run():
    b = _backend()
    list(b.run(_inp(loop_count=2)))
    res = b.get_result()
    assert res.report_md.startswith("#")
    assert len(res.metrics_history) == 3   # baseline + 2 loops


def test_validate_input_errors():
    errs = _backend().validate_input(_inp(loop_count=0))
    assert any("루프" in e for e in errs)


def test_get_result_before_run_raises():
    with pytest.raises(RuntimeError):
        _backend().get_result()
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_api_backend.py -v`
Expected: FAIL (ModuleNotFoundError: backend.api_backend).

- [ ] **Step 3: 구현** — `backend/api_backend.py`:
```python
"""ApiBackend — HTTP API를 통해 PipelineBackend 계약을 구현하는 프론트 클라이언트."""
from __future__ import annotations

import time
from typing import Iterator, List, Optional

import httpx

from backend.interface import PipelineInput, ProgressEvent, PipelineResult
from api import schema

_POLL_INTERVAL = 0.3


class ApiBackend:
    """run()/get_result()/validate_input()을 HTTP 호출로 수행. 대시보드는 그대로 사용."""

    def __init__(self, base_url: str, client: Optional[httpx.Client] = None,
                 poll_interval: float = _POLL_INTERVAL) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self._base, timeout=30.0)
        self._poll = poll_interval
        self._job_id: Optional[str] = None

    def validate_input(self, inp: PipelineInput) -> List[str]:
        r = self._client.post("/validate", json=schema.input_to_dict(inp))
        r.raise_for_status()
        return r.json()["errors"]

    def run(self, inp: PipelineInput) -> Iterator[ProgressEvent]:
        r = self._client.post("/jobs", json=schema.input_to_dict(inp))
        if r.status_code == 400:
            raise RuntimeError("입력 검증 실패: " + "; ".join(r.json().get("errors", [])))
        r.raise_for_status()
        self._job_id = r.json()["job_id"]
        after = 0
        while True:
            er = self._client.get(f"/jobs/{self._job_id}/events",
                                  params={"after": after})
            er.raise_for_status()
            data = er.json()
            for ev in data["events"]:
                yield schema.event_from_dict(ev)
            after = data["next"]
            if data["status"] == "failed":
                raise RuntimeError("백엔드 작업이 실패했습니다.")
            if data["status"] == "done":
                break
            time.sleep(self._poll)

    def get_result(self) -> PipelineResult:
        if self._job_id is None:
            raise RuntimeError("run()을 먼저 실행해야 결과를 얻을 수 있습니다.")
        r = self._client.get(f"/jobs/{self._job_id}/result")
        r.raise_for_status()
        return schema.result_from_dict(r.json())
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_api_backend.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**
```bash
git add backend/api_backend.py tests/test_api_backend.py
git commit -m "feat: ApiBackend HTTP client implementing PipelineBackend contract"
```

---

## Task 5: app.py 백엔드 선택 (환경변수)

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_backend_selection.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_app_backend_selection.py`:
```python
def test_get_backend_default_is_mock(monkeypatch):
    monkeypatch.delenv("HYPOLOOP_API_URL", raising=False)
    import app
    assert type(app.get_backend()).__name__ == "MockBackend"


def test_get_backend_is_api_when_env_set(monkeypatch):
    monkeypatch.setenv("HYPOLOOP_API_URL", "http://localhost:9999")
    import app
    assert type(app.get_backend()).__name__ == "ApiBackend"
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_app_backend_selection.py -v`
Expected: FAIL (현재 get_backend는 항상 MockBackend → 두 번째 테스트 실패).

- [ ] **Step 3: app.py 수정** — `import os`를 import 블록에 추가하고, `get_backend()`를 교체:
```python
def get_backend():
    """백엔드 주입 지점.

    HYPOLOOP_API_URL 환경변수가 있으면 HTTP ApiBackend, 없으면 인프로세스 MockBackend.
    """
    api_url = os.environ.get("HYPOLOOP_API_URL")
    if api_url:
        from backend.api_backend import ApiBackend
        return ApiBackend(api_url)
    return MockBackend()
```
(import 블록에 `import os` 한 줄 추가. 기존 `from backend.mock import MockBackend`는 유지.)

- [ ] **Step 4: 통과 확인 + 전체 회귀**

Run: `python -m pytest tests/test_app_backend_selection.py -v`
Expected: PASS (2 passed).
Run: `python -m pytest -q`
Expected: 전체 통과.

- [ ] **Step 5: Commit**
```bash
git add app.py tests/test_app_backend_selection.py
git commit -m "feat: select ApiBackend via HYPOLOOP_API_URL env (Mock fallback)"
```

---

## Task 6: E2E — 실제 서버 + 프론트 연결

**Files:** (없음 — 검증)

- [ ] **Step 1: 서버 실행(백그라운드)**

Run: `uvicorn api.server:app --port 8000 --log-level warning &`
확인: `curl -s http://localhost:8000/health` → `{"status":"ok"}`

- [ ] **Step 2: 서버 단독 E2E (curl)**

Run (한 줄씩):
```bash
JID=$(curl -s -X POST http://localhost:8000/jobs -H 'Content-Type: application/json' \
  -d '{"csv_path":"sample_data/sample.csv","loop_count":2,"data_card":{"target_column":"Survived","task_type":"classification","description":"t"},"llm_instruction":"가설"}' | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "job: $JID"
sleep 2
curl -s "http://localhost:8000/jobs/$JID/events?after=0" | python -c "import sys,json;d=json.load(sys.stdin);print('status',d['status'],'events',len(d['events']))"
curl -s "http://localhost:8000/jobs/$JID/result" | python -c "import sys,json;d=json.load(sys.stdin);print('report starts:', d['report_md'][:20])"
```
Expected: status done, events > 0, report starts with `# 분석 리포트`.

- [ ] **Step 3: 프론트를 API에 연결해 실행**

Run: `HYPOLOOP_API_URL=http://localhost:8000 streamlit run app.py --server.port 8501 --server.headless true`
확인(브라우저 또는 프리뷰):
- 샘플 CSV 업로드 → 분석 실행 → **라이브 대시보드가 동일하게 동작**(콘솔·지표 실시간). 이때 데이터는 HTTP를 통해 별도 서버 프로세스에서 옴.
- 완료 후 결과 화면 정상.
(스크린샷 캡처)

- [ ] **Step 4: 폴백 확인**

`HYPOLOOP_API_URL` 없이 `streamlit run app.py` 실행 → 기존처럼 인프로세스 Mock으로 동작(서버 불필요).

- [ ] **Step 5: 서버 종료**

Run: `pkill -f "uvicorn api.server:app"`

- [ ] **Step 6: 최종 회귀**

Run: `python -m pytest -q`
Expected: 전체 통과.

---

## 자체 점검 결과

- **스펙 커버리지**: 와이어 포맷(Task1=§3), 잡 스토어/백그라운드(Task2=§4·§6), 서버 엔드포인트(Task3=§3), ApiBackend 클라이언트(Task4=§4·§5), 환경변수 선택+폴백(Task5=§5), E2E·실행법(Task6=§9). 에러 처리(§7)는 Task2(failed 상태)·Task3(400/404/409/500)·Task4(예외)·테스트로 커버.
- **플레이스홀더**: 없음(모든 코드·명령·기대출력 명시).
- **타입 일관성**: `schema.*_to_dict/from_dict`(Task1) ↔ `JobStore`(Task2) ↔ `create_app/엔드포인트`(Task3) ↔ `ApiBackend`(Task4)에서 동일 시그니처 사용. `get_events`는 `{status,events,next}`, `get_result`는 `(status, payload)` 튜플로 일관. `ApiBackend(base_url, client, poll_interval)` 생성자 일관. `backend_factory: Callable[[], PipelineBackend]` 일관.
