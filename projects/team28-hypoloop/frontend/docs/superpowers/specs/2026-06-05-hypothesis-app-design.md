# Streamlit 프론트 재설계 — 프로젝트·가설 중심 (Hypo Loop)

작성일: 2026-06-05
담당: 정의찬 (UI / 프론트)
프로젝트: 28조 ML 자동화 에이전트 (hypoloop)

## 1. 목적

프론트를 **프로젝트·가설 중심**으로 재설계한다(스택은 Streamlit 유지). 사용자가 사이드바에서
프로젝트(현재 고정 1개)를 보고, 그 아래 가설을 추가하면, 에이전트가 실험하는 과정을 라이브로
보고, 완료되면 보고서를 보고, 대시보드 차트에서 가설별 최고 점수를 점으로 확인·클릭한다.

데이터는 **목(mock) store 계층**으로 먼저 구현하고(지금 완성·데모), 이후 `feat/backend`의 실제
API로 교체한다. 목 계층은 백엔드 계약을 미러링한다.

### 범위
- 포함: 사이드바(프로젝트 고정 + 가설 추가/목록), 대시보드 점수 차트(Plotly, 점 클릭→보고서),
  가설 등록 화면(입력 + 라이브 에이전트 활동), 보고서 화면, 목 store, 디자인 정리.
- 제외(이번): 프로젝트 추가/삭제(고정 1개), 가설 삭제, 실제 백엔드 연결(목으로 대체),
  에이전트 실제 학습(목 시뮬레이션), 인증/멀티유저.

## 2. 데이터 모델 & store 계층

`store/`에 Protocol + Mock 구현. feat/backend 계약 미러(교체 대비).

```python
@dataclass
class Project:        # 고정 1개
    project_id: str
    name: str

@dataclass
class Hypothesis:
    hypothesis_id: str
    project_id: str
    content: str
    max_experiments: int      # 최대 실험 길이
    parallel_count: int       # 병렬 횟수
    status: str               # "registered" | "running" | "done"
    best_score: float | None  # 0~1 (높을수록 좋음), 완료 전 None
    score_history: list[float]
    analysis_text: str
    report_md: str

@dataclass
class AgentEvent:             # 라이브 활동 1건
    phase: str                # 단계명(계획/EDA/실험설계/학습/평가/보고서 등)
    kind: str                 # "step" | "tool" | "code" | "log" | "metric"
    text: str
    score: float | None       # kind=="metric"일 때 0~1 점수
```

**HypoStore (Protocol)** — feat/backend 매핑:
| store 메서드 | 의미 | 실제 백엔드 대응 |
| --- | --- | --- |
| `get_project()` | 고정 프로젝트 | (고정) |
| `list_hypotheses()` | 가설 목록 | (백엔드 목록 GET 필요 — 현재 없음) |
| `create_hypothesis(content, max_experiments, parallel_count)` | 가설 등록 | `POST /projects/{id}/hypotheses` |
| `run(hypothesis_id) -> Iterator[AgentEvent]` | 실험 시작+라이브 활동 | `POST /hypotheses/{id}/ready` + status 폴링/스트림 |
| `get_report(hypothesis_id) -> Hypothesis` | 완료 보고서 데이터 | `GET /hypotheses/{id}/report` |
| `best_scores() -> list[(hypothesis, score)]` | 차트용 최고점 | report 집계 |

**MockStore**: 가설을 `st.session_state`에 보관. `run()`은 클로드식 상세 활동을 시뮬레이션으로
yield하고(계획→EDA→실험설계→학습→평가→보고서, tool/code/log/metric 섞어서), 매 실험마다
점수(0~1)를 생성, 완료 시 best_score/score_history/analysis_text/report_md 채움.
점수는 RMSE를 0~1 점수(높을수록 좋음)로 변환한 값으로 취급.

## 3. 앱 셸 + 사이드바

- `app.py`: `st.set_page_config(layout="wide")`, 테마 CSS 주입, 사이드바 렌더, 본문 라우팅.
- **사이드바**(`ui/sidebar.py`, Streamlit 기본 접기/펼치기):
  - 상단: 프로젝트 이름(고정 표시)
  - 그 아래: 가설 목록 — 각 항목은 버튼(가설 요약 + 상태 배지). 클릭 시 선택 가설 설정 + 적절한 뷰로 이동(done→report, 그 외→해당 상태).
  - 하단: **[+ 새 가설]** 버튼 → `view="register"`.
- 본문 라우팅: `st.session_state.view` ∈ {`dashboard`, `register`, `report`}. 기본 `dashboard`.

## 4. 대시보드 (`ui/dashboard_view.py`)

- 제목: "가설별 최고 점수".
- **Plotly 가로 점 차트**: y=가설(번호/요약), x=best_score(0~1, 높을수록 우측). `status=="done"`
  가설만 점 표시. 점 없으면 안내문.
- **점 클릭 → 보고서**: `st.plotly_chart(..., on_select="rerun")`의 선택 이벤트에서 클릭된 점의
  hypothesis_id를 읽어 `selected_hypothesis` 설정 + `view="report"`.
- 순수 로직 `scores_to_figure_data(hypotheses)` 분리(테스트 대상): 점 좌표/라벨/id 매핑 생성.

## 5. 가설 등록 (`ui/hypothesis_register.py` + `ui/agent_status.py`)

- 레이아웃: **상단=라이브 에이전트 활동 영역**, **하단=가설 입력 폼**.
- 입력 폼: 가설 내용(textarea), 최대 실험(number), 병렬 수(number), [실행] 버튼.
- [실행] 시: `store.create_hypothesis(...)` → `store.run(id)` 이벤트를 순회하며 상단 콘솔에 실시간
  렌더(`ui/agent_status.py`: step/tool/code/log/metric을 아이콘 없이 라벨로 구분, 코드 블록 표시).
  진행률·현재 단계 표시. 완료되면 store에 보고서 저장 후 `view="report"`로 전환.
- 라이브 상태 누적 로직은 순수 클래스(`AgentActivityState`)로 분리(테스트): 이벤트→콘솔 항목/현재
  단계/점수 누적, 콘솔 최근 N개 제한.

## 6. 보고서 (`ui/report_view.py`)

- 선택 가설의: 가설 내용, 최고 점수(metric 카드), 점수 추이 차트(score_history), 실험 결과 분석
  텍스트, (선택) 다운로드. "대시보드로" 버튼.

## 7. 통합 경계 / 트리거

- 지금: `MockStore`가 전체 시뮬레이션. 교체 시 `BackendStore`(httpx)가 `POST 가설`→`POST /ready`
  호출 후 status 폴링. **에이전트 호출(트리거) 자체는 백엔드 담당**(프론트는 `/ready`까지).
- `app.py`의 `get_store()` 한 곳에서 Mock/Backend 선택(환경변수, 기본 Mock).

## 8. 디자인

- 눈 편한 **부드러운 뉴트럴 배경 + 단일 포인트 컬러**(예: 차분한 인디고/슬레이트), 둥근 모서리,
  넉넉한 여백, **이모지 미사용**(기존 테마의 이모지·🤖 타이틀 제거). 상태 배지는 텍스트/색으로.
- `ui/theme.py` 재정리: 토큰 + CSS 주입(폰트 Inter, 버튼/카드/사이드바 스타일), 이모지 제거.

## 9. 파일 구조

```
app.py                         # 셸: page_config, 테마, 사이드바, 라우팅, get_store()
store/__init__.py
store/types.py                 # Project/Hypothesis/AgentEvent
store/base.py                  # HypoStore Protocol
store/mock.py                  # MockStore (세션 보관 + 시뮬레이션 run)
ui/theme.py                    # 토큰 + CSS (이모지 제거)
ui/sidebar.py                  # 프로젝트 고정 + 가설 목록 + 새 가설
ui/dashboard_view.py           # 점수 차트(Plotly) + 점 클릭→보고서
ui/agent_status.py             # 라이브 에이전트 콘솔 + AgentActivityState(순수)
ui/hypothesis_register.py      # 입력 폼 + 라이브 영역
ui/report_view.py              # 보고서
tests/                         # store mock / scores_to_figure_data / AgentActivityState
requirements.txt               # streamlit, pandas, plotly, pytest
```
> 기존 단일플로우 UI(input_form, 기존 dashboard_view/dashboard_logic, report_viewer, backend/*,
> api/*)는 이 앱 모델과 맞지 않아 **새 구조로 대체**한다. 재사용 가능한 패턴(라이브 콘솔, 보고서,
> 테마)은 새 컴포넌트로 옮겨 정리한다. (API 서버/ApiBackend 등은 별도 기능이므로 삭제하지 않되
> 새 app.py 흐름에서는 사용하지 않는다.)

## 10. 테스트

- **순수 로직**: MockStore(create/list/run 이벤트 시퀀스/best_scores/get_report), `AgentActivityState`
  (이벤트 분류·누적·콘솔 제한·점수), `scores_to_figure_data`(좌표/id 매핑, done만 포함).
- **계약**: store Protocol 충족(MockStore가 HypoStore 만족), AgentEvent/Hypothesis 형태.
- **렌더**: Streamlit 화면은 수동 확인(스크린샷). Plotly 클릭 이벤트는 수동 확인.

## 11. 제약 / 원칙

- 목 store는 세션 보관(새로고침 시 초기화) — 데모 범위. 실제 영속은 백엔드 연결 시.
- store 계약은 feat/backend에 맞춰 두어 교체 비용 최소화.
- Plotly 추가 의존성 필요(requirements). Streamlit 1.56의 `on_select` 사용.
- 이모지 미사용, 차분한 디자인 일관 유지.
