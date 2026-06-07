# ML 자동화 에이전트 — UI/프론트 설계서

작성일: 2026-06-03
담당: 정의찬 (담당 B — UI / 프론트)
프로젝트: 28조 ML 파이프라인 자동화 AI 에이전트

## 1. 목적과 범위

ML 파이프라인 자동화 에이전트의 **사용자 대면 프론트엔드**를 구현한다. 두 화면이
핵심이다.

1. **입력 폼 화면** — CSV 업로드, 루프 횟수, 데이터 카드, 언어모델 입력
2. **보고서 뷰어 화면** — 최종 MD 보고서, 성능 지표 시각화, 생성 코드, 실시간 진행 상태

백엔드(SQL 적재, LangGraph 에이전트, MLflow, 리포트 생성)는 다른 팀원이 병렬로
개발 중이다. 따라서 UI는 **백엔드와 합의한 인터페이스 계약에만 의존**하고, 지금은
Mock 구현으로 완성·테스트한다. 나중에 Mock만 실제 백엔드로 교체한다.

### 범위 밖 (이 스펙에서 제외)

- 실제 SQLite 적재 로직, LangGraph 에이전트, MLflow 연동 (백엔드 팀 담당)
- 인증, 다중 사용자, 클라우드 배포

## 2. 아키텍처 — 계약 경계가 핵심

```
사용자 ─→ Streamlit UI ─→ [PipelineBackend 인터페이스] ─→ Mock 구현 (현재)
                                  ▲                          ↓ 나중에 교체
                                  └──────────────── 실제 백엔드 (팀)
```

UI는 `PipelineBackend` 추상 인터페이스에만 의존한다. 백엔드 팀은 이 인터페이스만
구현하면 통합된다. 이 인터페이스 파일이 **두 팀의 합의 계약서** 역할을 한다.

## 3. 데이터 계약 (UI ↔ 백엔드)

`backend/interface.py`에 dataclass로 정의한다.

```python
# --- 입력 ---
@dataclass
class DataCard:
    target_column: str          # 예측 대상 컬럼
    task_type: str              # "classification" | "regression"
    description: str            # 데이터셋 자유 설명

@dataclass
class PipelineInput:
    csv_path: str               # 업로드된 CSV의 저장 경로
    loop_count: int             # 성능 개선 루프 횟수 (1~상한)
    data_card: DataCard
    llm_instruction: str        # 가설·목표·평가산식 자유 텍스트

# --- 진행 상태 (스트리밍 이벤트) ---
@dataclass
class ProgressEvent:
    stage: str                  # PIPELINE_STAGES 중 하나
    loop_index: int             # 현재 루프 (0=베이스라인)
    status: str                 # "running" | "done" | "failed"
    message: str                # 사용자에게 보일 한 줄 설명

# --- 최종 결과 ---
@dataclass
class MetricRecord:
    loop_index: int
    metric_name: str            # 예: "accuracy", "rmse"
    baseline: float             # 베이스라인 값
    value: float                # 해당 루프 값

@dataclass
class PipelineResult:
    report_md: str              # 최종 마크다운 보고서
    final_code: str             # 실행 가능한 Python 코드
    metrics_history: list[MetricRecord]
    experiment_yaml: str        # 백엔드가 생성한 yml 실험 파일 내용
```

### 인터페이스

```python
PIPELINE_STAGES = ["계획수립", "EDA", "베이스라인", "피처엔지니어링", "튜닝", "리포트"]

class PipelineBackend(Protocol):
    def validate_input(self, inp: PipelineInput) -> list[str]:
        """입력 검증. 문제 메시지 리스트 반환(빈 리스트면 통과)."""

    def run(self, inp: PipelineInput) -> Iterator[ProgressEvent]:
        """파이프라인 실행. 진행 이벤트를 순차 스트리밍(yield)."""

    def get_result(self) -> PipelineResult:
        """run() 완료 후 최종 결과 반환."""
```

`Mock` 구현(`backend/mock.py`)은 이 인터페이스를 따라 가짜 이벤트를 순차 yield하고
샘플 리포트/지표/코드를 반환한다. (지연은 작은 `time.sleep`으로 흉내)

## 4. 파일 구조 (각 파일은 하나의 책임)

```
app.py                      # Streamlit 진입점 + 화면 라우팅(입력↔진행↔보고서)
ui/
  __init__.py
  input_form.py             # 입력 폼 화면 렌더링 + 검증 호출
  progress_view.py          # 진행 상태 실시간 표시
  report_viewer.py          # 보고서 뷰어(탭: 리포트/지표/코드/다운로드)
  theme.py                  # 공통 스타일·헬퍼(헤더, 카드, 색상 토큰)
backend/
  __init__.py
  interface.py              # ★ PipelineBackend 계약 + dataclass (팀 합의 파일)
  mock.py                   # Mock 구현
sample_data/
  sample.csv                # 테스트용 샘플 CSV (예: 타이타닉 축약본)
  sample_report.md          # Mock이 반환할 샘플 보고서
tests/
  test_interface.py         # dataclass/계약 형태 검증
  test_mock.py              # Mock이 계약대로 이벤트·결과 내는지
  test_input_form.py        # 입력 검증 로직(타깃 컬럼 존재 등)
requirements.txt
README.md                   # 실행법 + 백엔드 통합 가이드
```

## 5. 화면 흐름과 상태 관리

세 화면을 `st.session_state.view` 값(`"input"` → `"running"` → `"report"`)으로
전환한다. 단일 페이지 안에서 상태에 따라 다른 컴포넌트를 렌더링한다.

```
[입력 화면]
  CSV 업로드 → pandas로 읽어 컬럼·미리보기 표시
  데이터 카드: 타깃 컬럼(업로드 컬럼에서 선택), 태스크 종류(라디오), 설명(textarea)
  루프 횟수: number_input (1~상한, 기본값 제공)
  언어모델 입력: textarea (가설·목표·평가산식, placeholder로 예시 안내)
  [실행] 클릭 → validate_input → 통과 시 view="running"
        ↓
[진행 화면]
  backend.run() 이벤트를 순회하며 단계별·루프별 상태를 실시간 갱신
  단계 체크리스트 + 현재 루프/전체 루프 진행률 표시
  완료 시 view="report"
        ↓
[보고서 화면]
  탭1 리포트   : st.markdown 렌더링 + .md 다운로드 버튼
  탭2 성능지표 : metrics_history를 라인차트 + 테이블(베이스라인 대비 Delta 강조)
  탭3 코드     : st.code(final_code) + .py 다운로드 버튼
  탭4 실험설정 : experiment_yaml 표시 + .yml 다운로드
  [새 분석 시작] → 상태 초기화 후 view="input"
```

입력값은 `st.session_state`에 보관해 재실행(rerun) 사이에 유지한다.

## 6. UI/UX 품질 기준

깔끔하고 사용자가 불편하지 않은 화면을 위해 다음을 지킨다.

- **명확한 단계감**: 상단에 "1 입력 → 2 분석 → 3 결과" 스텝 표시로 현재 위치를 항상 보여준다.
- **점진적 노출**: CSV 업로드 전에는 데이터 카드 필드를 비활성/숨김 처리해 빈 화면의 혼란을 줄인다.
- **즉각적 피드백**: 업로드 즉시 행·열 수와 미리보기 표시. 검증 실패 시 어떤 필드가 왜 문제인지 그 필드 옆에 인라인으로 안내.
- **안전한 기본값**: 루프 횟수 기본값·상한, 태스크 종류 자동 추정(타깃 컬럼 dtype 기반)으로 입력 부담을 줄인다.
- **되돌아가기 가능**: 진행/결과 화면에서 입력 화면으로 돌아갈 수 있고, 입력값은 보존된다.
- **실시간 진행 표시**: `st.status`/진행률로 "지금 무엇을 하는 중인지"를 항상 보여 멈춘 듯한 느낌을 없앤다.
- **결과 신뢰성 고지**: 보고서 화면 상단에 "제한된 데이터·환경 결과이므로 프로덕션 적용 전 검토 필요" 경계 문구를 항상 노출(기획서 정책).
- **접근성**: 색만으로 정보를 전달하지 않고 라벨/아이콘 병기, 충분한 대비, 키보드로 모든 입력 도달 가능.
- **일관된 스타일**: 색상·간격·폰트 토큰을 `ui/theme.py`에 모아 화면 간 일관성 유지.

구현 후 `web-design-guidelines` 스킬로 UI를 점검한다.

## 7. 구현 흐름 체크리스트 (순서)

병렬 협업의 계약 경계부터 만들고, 안에서 바깥으로 쌓는다.

- [ ] **1. 프로젝트 골격**: `requirements.txt`(streamlit, pandas, pyyaml, pytest), 폴더 구조, 빈 모듈 생성
- [ ] **2. 데이터 계약**: `backend/interface.py`에 dataclass + `PipelineBackend` Protocol + `PIPELINE_STAGES` 정의 — *팀과 먼저 공유할 산출물*
- [ ] **3. 계약 테스트**: `tests/test_interface.py`로 dataclass 형태 고정
- [ ] **4. Mock 백엔드**: `backend/mock.py` — 검증/이벤트 스트리밍/샘플 결과. `tests/test_mock.py`로 계약 준수 검증
- [ ] **5. 샘플 데이터**: `sample_data/sample.csv`, `sample_data/sample_report.md`
- [ ] **6. 공통 테마**: `ui/theme.py` — 스텝 헤더, 카드, 색상 토큰, 경계 문구 헬퍼
- [ ] **7. 입력 폼**: `ui/input_form.py` — 업로드·미리보기·데이터 카드·루프·LLM 입력·검증. `tests/test_input_form.py`로 검증 로직 테스트
- [ ] **8. 진행 화면**: `ui/progress_view.py` — 이벤트 순회·단계 체크리스트·진행률
- [ ] **9. 보고서 뷰어**: `ui/report_viewer.py` — 4개 탭(리포트/지표/코드/실험설정)·다운로드
- [ ] **10. 앱 조립**: `app.py` — 세션 상태 라우팅으로 세 화면 연결
- [ ] **11. E2E 확인**: Mock으로 입력→진행→보고서 전체 흐름 수동 실행 및 스크린샷 확인
- [ ] **12. UI 점검**: `web-design-guidelines` 스킬로 접근성·UX 점검 후 보완
- [ ] **13. README**: 실행법 + 백엔드 통합 가이드(인터페이스 구현 방법) 작성

## 8. 테스트 전략

- **단위**: dataclass 계약, Mock의 이벤트·결과, 입력 검증 로직(타깃 컬럼 존재, 루프 범위, 빈 입력)
- **통합(E2E)**: Mock 백엔드로 입력→진행→보고서 전 흐름이 끊김 없이 동작하는지 수동 + 가능하면 자동 확인
- UI 렌더링 자체보다 **로직(검증·계약·파싱)** 을 우선 자동 테스트한다.

## 9. 백엔드 팀과의 통합 지점

- 합의 파일은 `backend/interface.py` 하나. 백엔드 팀은 `PipelineBackend`를 구현한
  클래스를 제공하고, `app.py`에서 `Mock()` 대신 그 클래스를 주입하면 통합 완료.
- 계약 변경이 필요하면 이 파일을 함께 수정·리뷰한다(양 팀 영향 지점).
