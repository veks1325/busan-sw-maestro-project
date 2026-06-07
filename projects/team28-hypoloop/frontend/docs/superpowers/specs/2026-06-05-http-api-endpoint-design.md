# HTTP API 엔드포인트 — 설계서 (프론트↔백엔드 분리)

작성일: 2026-06-05
담당: 정의찬 (UI / 프론트)
프로젝트: 28조 ML 자동화 에이전트 (hypoloop)

## 1. 목적 / 배경

팀이 프론트 / 백엔드 / ML로 나뉘어 있다. 지금은 프론트가 백엔드를 **같은 프로세스에서
함수로 직접 호출**(인프로세스)한다. 이를 **HTTP API 엔드포인트로 분리**해, 백엔드+ML이
프론트와 **별개 프로그램(서버)** 으로 돌게 한다. 그러면:

- 프론트가 꺼져도 서버는 돌고, 다른 머신/서비스에 둘 수 있다.
- ML팀이 프론트를 건드리지 않고 **서버 뒷단에 자기 구현을 계속 붙일 수 있다.**

핵심: 프론트↔백엔드 경계가 **함수 호출 → HTTP 호출**로 바뀐다. 진짜 함수 호출(학습 등)은
서버 안쪽(백엔드/ML 영역)에서만 일어난다.

## 2. 작업 범위

전체 세트를 만든다(프론트가 지금 바로 엔드포인트 상대로 개발/데모 가능):

1. **HTTP API 계약** — 엔드포인트 + JSON 와이어 포맷
2. **참조 FastAPI 서버** — 인메모리 잡 스토어, 백그라운드 실행. 현재 `MockBackend` 내장.
3. **프론트 HTTP 클라이언트** — `ApiBackend`(기존 `PipelineBackend` 계약 구현)

백엔드/ML팀은 서버 안의 `PipelineBackend` 구현만 실제(LangGraph+Solar+ML)로 교체한다.
HTTP 계약·프론트 코드는 그대로.

### 범위 밖
- 실제 ML 학습/에이전트, 인증, 다중 사용자, 영속 잡 스토어(DB), 배포(이번 범위 아님).
- 이벤트 전달은 **비동기 잡 + 폴링**으로 한정(SSE/WebSocket 제외).

## 3. HTTP API 계약

비동기 잡 모델 + 폴링.

| 메서드 | 경로 | 요청 | 응답 |
| --- | --- | --- | --- |
| `GET` | `/health` | — | `{"status":"ok"}` |
| `POST` | `/validate` | PipelineInput(JSON) | `{"errors": [str, ...]}` (빈 배열이면 통과) |
| `POST` | `/jobs` | PipelineInput(JSON) | 검증 통과: `201 {"job_id": str}` + 백그라운드 실행 시작. 검증 실패: `400 {"errors":[...]}` |
| `GET` | `/jobs/{job_id}/events?after=N` | — | `{"status":"running\|done\|failed","events":[ProgressEvent,...],"next":M}` — 인덱스 N 이후 이벤트만. `next`=다음 폴링에 쓸 인덱스 |
| `GET` | `/jobs/{job_id}/result` | — | 완료 시 `200 PipelineResult(JSON)`. 미완료 `409`. 실패 `500 {"error":str}`. 없는 잡 `404` |

### 와이어 포맷 (JSON) — `api/schema.py` 단일 출처

```
PipelineInput  = {csv_path, loop_count, data_card:{target_column, task_type, description}, llm_instruction}
ProgressEvent  = {stage, loop_index, status, message, kind, detail, metric}   # metric: MetricRecord|null
MetricRecord   = {loop_index, metric_name, baseline, value}
PipelineResult = {report_md, final_code, metrics_history:[MetricRecord,...], experiment_yaml}
```

`api/schema.py`는 각 dataclass에 대해 `to_dict()` / `from_dict()`를 제공한다(직렬화 단일 출처).
서버와 ApiBackend가 모두 이 모듈만 사용한다.

## 4. 컴포넌트 (파일)

```
api/__init__.py
api/schema.py            # dataclass ↔ dict 직렬화(PipelineInput/ProgressEvent/MetricRecord/PipelineResult)
api/job_store.py         # 인메모리 잡 스토어 + 백그라운드 실행(스레드). PipelineBackend 주입.
api/server.py            # FastAPI 앱 + 엔드포인트. job_store 사용.
backend/api_backend.py   # ApiBackend(PipelineBackend): HTTP 클라이언트(httpx)
app.py                   # get_backend(): HYPOLOOP_API_URL 있으면 ApiBackend, 없으면 MockBackend
requirements.txt         # fastapi, uvicorn, httpx 추가
tests/test_api_schema.py
tests/test_api_server.py
tests/test_api_backend.py
```

각 파일 책임:
- `schema.py`: 순수 직렬화. 단위 테스트(라운드트립).
- `job_store.py`: `submit(inp) -> job_id`, `get_events(job_id, after)`, `get_result(job_id)`, 상태 관리.
  백그라운드 스레드가 `backend.run(inp)`를 순회하며 이벤트를 잡에 적재, 완료 시 `get_result()`로 결과 저장.
- `server.py`: 얇은 HTTP 레이어. 검증/잡 제출/폴링/결과를 job_store에 위임.
- `api_backend.py`: `validate_input`→POST /validate, `run`→POST /jobs 후 events 폴링하며 yield,
  `get_result`→GET /jobs/{id}/result. 기존 `PipelineBackend` 계약 100% 구현.

## 5. 프론트 통합 — 대시보드 그대로

`ApiBackend`가 `PipelineBackend`를 그대로 구현하므로 **대시보드/app.py 로직은 안 바뀐다.**
`run(inp)`는 제너레이터로, 내부에서 폴링하며 `ProgressEvent`를 yield한다(대시보드의
`for ev in backend.run(inp)` 루프 그대로).

`app.py get_backend()`:
```
HYPOLOOP_API_URL 환경변수가 있으면  → ApiBackend(base_url)
없으면                              → MockBackend()  (인프로세스 폴백, 단독 실행 유지)
```

## 6. 데이터 흐름

```
Streamlit(ApiBackend)            FastAPI(server + job_store)         PipelineBackend(Mock→ML)
  validate_input → POST /validate ─────────────────────────────────> validate_input()
  run() → POST /jobs ──────────────> job_store.submit():
                                        백그라운드 스레드 start
                                          for ev in backend.run(inp): 이벤트 적재
  while not done:                         ...
    GET /events?after=N ◀── 새 이벤트들 (yield ProgressEvent)
  get_result() → GET /jobs/{id}/result ◀── PipelineResult
```

폴링 간격은 ApiBackend 상수(예: 0.3s). 서버는 이벤트를 인덱스로 관리해 `after`로 증분 전달.

## 7. 에러 처리

- 검증 실패: `/validate`·`/jobs`가 `errors` 반환 → 프론트가 입력 화면에 안내(기존 흐름).
- 잡 실행 중 예외: job_store가 상태 `failed`로 두고, `/events`의 status=failed, `/result`는 500+error.
  ApiBackend.run()은 failed 감지 시 예외를 던지고, app.py의 기존 try/except가 사용자에게 안내.
- 폴링 연결 실패(서버 다운 등): ApiBackend가 httpx 예외 → app.py try/except가 안내.
- 잡 미완료에 result 요청: 409 → ApiBackend는 run() 완료 후에만 result 호출하므로 정상 흐름에선 발생 안 함.

## 8. 테스트

- **schema 라운드트립**(순수): 각 dataclass를 to_dict→from_dict 하면 동일. metric None/값 케이스.
- **서버**(FastAPI `TestClient`): POST /jobs → events 폴링 → done → result. 검증 실패 400. 없는 잡 404.
- **ApiBackend**(httpx `ASGITransport`로 서버를 인프로세스 호출, 네트워크 없이): `run()`이 이벤트를
  yield하고 모든 PIPELINE_STAGES 등장, `get_result()`가 PipelineResult 반환, 검증 에러 경로.
- 기존 테스트 회귀: app.py get_backend()가 환경변수 없을 때 MockBackend 유지.

## 9. 의존성 / 실행

- 추가: `fastapi`, `uvicorn[standard]`, `httpx`.
- 서버 실행: `uvicorn api.server:app --port 8000`
- 프론트를 API에 연결: `HYPOLOOP_API_URL=http://localhost:8000 streamlit run app.py`
- 환경변수 없이 실행하면 기존처럼 인프로세스 Mock으로 동작.

## 10. 제약 / 원칙

- 잡 스토어는 인메모리(프로세스 재시작 시 소실) — 데모/단일 서버 범위. DB 영속화는 다음 단계.
- 직렬화는 `api/schema.py` 한 곳에서만(와이어 포맷 드리프트 방지).
- `ApiBackend`는 `PipelineBackend` 계약을 깨지 않는다(대시보드 비침투).
- 서버의 `PipelineBackend`는 주입식 — 기본 Mock, 통합 시 실제 구현으로 교체.

## 11. 보안 / 운영 주의 (실제 배포 전 필수)

- **csv_path 임의 파일 읽기**: `csv_path`가 HTTP로 들어오는 서버측 경로다. 백엔드가 그 경로를
  `pd.read_csv`로 연다 → 경로 탈출/임의 파일 읽기(나아가 URL이면 SSRF) 위험. 참조 서버는
  작업 디렉터리 안쪽인지 검사(`_is_safe_csv_path`)로 1차 방어한다. **실제 배포 시에는 경로 대신
  업로드 핸들/불투명 ID 모델**(클라이언트가 바이트 업로드 → 서버가 샌드박스에 저장 후 토큰 참조)로
  바꾸는 것을 권장. 이 경우 `PipelineInput.csv_path` 계약도 함께 재검토.
- **잡 스토어 무한 증가**: 인메모리 `_jobs`는 만료/제거가 없어 잡이 영구 적재된다. 단일 데모 서버엔
  무방하나, 실제에선 TTL/최대 개수 제거 필요.
- **인증/멀티유저 없음**: 누구나 잡을 제출/조회 가능. 배포 시 인증·격리 필요.
