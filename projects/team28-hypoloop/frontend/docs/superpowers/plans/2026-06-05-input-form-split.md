# 입력 폼 분리 + 데이터 카드 컬럼 설명 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 입력 폼에서 가설과 평가산식을 두 칸으로 분리하고, 데이터 카드를 컬럼별 설명(데이터 사전) 입력으로 바꾼다.

**Architecture:** 계약(`PipelineInput`)의 `llm_instruction`을 `hypothesis`로 이름 변경하고 `metric` 필드를 추가한다(파급: schema/mock/tests). 입력 폼은 한 칸이던 입력을 데이터 카드(컬럼 템플릿 자동 채움)·가설·평가산식 세 칸으로 나눈다.

**Tech Stack:** Python 3.10, Streamlit 1.56, pandas, pytest

참고 스펙: `docs/superpowers/specs/2026-06-05-input-form-split-design.md`
작업 위치: `/Users/justice/Desktop/AI 교육` (루트 레이아웃). 로컬엔 validation.py·data_layer_backend.py 없음.

---

## 파일 구조

```
backend/interface.py   # 수정: PipelineInput.llm_instruction → hypothesis, metric 추가
api/schema.py          # 수정: 직렬화 키 hypothesis/metric
backend/mock.py        # 수정: validate·report에서 inp.hypothesis 사용
ui/input_form.py       # 수정: column_template 헬퍼 + 데이터카드/가설/평가산식 3칸 + build_pipeline_input
tests/                 # 수정: test_interface, test_mock, test_api_server, test_input_form
```

---

## Task 1: 계약 이름 변경 + metric 추가 (interface/schema/mock + 테스트)

이름 변경은 모든 사용처를 한 번에 고쳐야 하므로 한 태스크로 묶는다.

**Files:**
- Modify: `backend/interface.py`, `api/schema.py`, `backend/mock.py`
- Modify: `tests/test_interface.py`, `tests/test_mock.py`, `tests/test_api_server.py`

- [ ] **Step 1: 테스트를 새 계약으로 갱신(먼저 실패하게)**

`tests/test_interface.py` — `test_pipeline_input_fields`를 다음으로 교체:
```python
def test_pipeline_input_fields():
    card = DataCard(target_column="y", task_type="regression", description="d")
    inp = PipelineInput(csv_path="/tmp/a.csv", loop_count=3,
                        data_card=card, hypothesis="가설", metric="rmse")
    assert inp.loop_count == 3
    assert inp.hypothesis == "가설"
    assert inp.metric == "rmse"


def test_pipeline_input_metric_default():
    card = DataCard(target_column="y", task_type="regression", description="d")
    inp = PipelineInput(csv_path="/tmp/a.csv", loop_count=1,
                        data_card=card, hypothesis="가설")
    assert inp.metric == ""
```

`tests/test_mock.py` — `make_input` 함수의 `llm_instruction="가설 검증"` 을
`hypothesis="가설 검증"` 으로 변경:
```python
def make_input(csv_path, loop_count=2, target="Survived"):
    card = DataCard(target_column=target, task_type="classification",
                    description="테스트")
    return PipelineInput(csv_path=csv_path, loop_count=loop_count,
                         data_card=card, hypothesis="가설 검증")
```
또한 같은 파일에서 회귀 테스트의 PipelineInput 생성에 `llm_instruction=`가 있으면
`hypothesis=`로 바꾼다. (예: `test_final_code_uses_regressor_for_regression`의
`PipelineInput(..., llm_instruction="가설")` → `hypothesis="가설"`.)

`tests/test_api_server.py` — `INPUT` dict의 `"llm_instruction": "가설"` 을
`"hypothesis": "가설"` 으로 변경(같은 파일 내 모든 INPUT 사용처 자동 반영).

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_interface.py tests/test_mock.py tests/test_api_server.py -q`
Expected: FAIL (PipelineInput에 hypothesis/metric 없음 → TypeError).

- [ ] **Step 3: interface.py 수정** — `PipelineInput` 정의를 교체:
```python
@dataclass
class PipelineInput:
    csv_path: str                 # 업로드된 CSV 저장 경로
    loop_count: int               # 성능 개선 루프 횟수
    data_card: DataCard
    hypothesis: str               # 사용자 가설
    metric: str = ""              # 평가산식(예: accuracy). 자유 텍스트, 선택
```

- [ ] **Step 4: api/schema.py 수정** — `input_to_dict`/`input_from_dict`의 llm_instruction을 교체:

`input_to_dict`의 마지막 키를:
```python
        "hypothesis": inp.hypothesis,
        "metric": inp.metric,
    }
```
`input_from_dict`의 PipelineInput 생성을:
```python
        hypothesis=d["hypothesis"],
        metric=d.get("metric", ""),
    )
```

- [ ] **Step 5: backend/mock.py 수정** — 두 곳:

(a) validate_input의 빈 가설 검사(현재 `if not inp.llm_instruction.strip():`)를:
```python
        if not inp.hypothesis.strip():
            errors.append("가설을 작성해주세요.")
```
(b) `_build_result`의 리포트 가설 줄(현재 `f"## 사용자 가설\n\n> {inp.llm_instruction}\n\n"`)을:
```python
            f"## 사용자 가설\n\n> {inp.hypothesis}\n\n"
            f"## 평가산식\n\n> {inp.metric or '미지정'}\n\n"
```

- [ ] **Step 6: 통과 확인 + 전체 회귀**

Run: `python -m pytest tests/test_interface.py tests/test_mock.py tests/test_api_server.py -q`
Expected: PASS.
Run: `python -m pytest -q`
Expected: 전체 통과(positional로 PipelineInput을 만드는 test_api_backend/test_api_job_store/test_api_schema는 4번째 위치 인자가 hypothesis로 매핑되어 그대로 통과).

- [ ] **Step 7: Commit**
```bash
git add backend/interface.py api/schema.py backend/mock.py tests/test_interface.py tests/test_mock.py tests/test_api_server.py
git commit -m "refactor: rename PipelineInput.llm_instruction -> hypothesis, add metric"
```

---

## Task 2: 입력 폼 3칸 분리 + 컬럼 템플릿

**Files:**
- Modify: `ui/input_form.py`
- Test: `tests/test_input_form.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_input_form.py`에 추가하고, 기존
`test_build_pipeline_input_shape`를 새 시그니처로 교체:
```python
from ui.input_form import infer_task_type, build_pipeline_input, column_template
from backend.interface import PipelineInput


def test_column_template_one_line_per_column():
    assert column_template(["Survived", "Pclass"]) == "Survived : \nPclass : \n"


def test_column_template_empty():
    assert column_template([]) == ""


def test_build_pipeline_input_shape():
    inp = build_pipeline_input(
        csv_path="/tmp/x.csv", loop_count=3, target_column="y",
        task_type="regression", description="Survived : 생존",
        hypothesis="가설", metric="rmse",
    )
    assert isinstance(inp, PipelineInput)
    assert inp.hypothesis == "가설"
    assert inp.metric == "rmse"
    assert inp.data_card.description == "Survived : 생존"


def test_build_pipeline_input_metric_optional():
    inp = build_pipeline_input(
        csv_path="/tmp/x.csv", loop_count=1, target_column="y",
        task_type="classification", description="d", hypothesis="가설",
    )
    assert inp.metric == ""
```
(기존 `from ui.input_form import infer_task_type, build_pipeline_input` 라인은 위
import로 대체.)

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_input_form.py -q`
Expected: FAIL (column_template 없음 / build_pipeline_input 시그니처 불일치).

- [ ] **Step 3: input_form.py 수정**

(a) `column_template` 헬퍼 추가(파일 상단의 다른 순수 함수 근처):
```python
def column_template(columns) -> str:
    """CSV 컬럼명으로 데이터 카드 템플릿 생성: 'col : \\n' 한 줄씩."""
    return "".join(f"{c} : \n" for c in columns)
```

(b) `build_pipeline_input` 시그니처/본문 교체:
```python
def build_pipeline_input(csv_path: str, loop_count: int, target_column: str,
                         task_type: str, description: str, hypothesis: str,
                         metric: str = "") -> PipelineInput:
    """폼 값들을 PipelineInput으로 조립."""
    card = DataCard(target_column=target_column, task_type=task_type,
                    description=description)
    return PipelineInput(csv_path=csv_path, loop_count=loop_count,
                         data_card=card, hypothesis=hypothesis, metric=metric)
```

(c) `render`의 입력 위젯 3개 교체 — 현재의 `description = st.text_area(...)` 와
`llm_instruction = st.text_area(...)` 블록을 다음으로 교체:
```python
    # 데이터 카드 — 각 컬럼 설명(업로드 컬럼으로 템플릿 자동 채움)
    desc_key = "datacard_desc"
    if st.session_state.get("_desc_cols") != columns:
        st.session_state["_desc_cols"] = columns
        st.session_state[desc_key] = column_template(columns)
    description = st.text_area(
        "데이터 카드 — 각 컬럼 설명 (컬럼명 : 설명)", key=desc_key, height=200,
        help="각 컬럼이 무엇인지 한 줄씩 적어주세요. "
             "예) Survived : 생존 여부 (0=사망, 1=생존)",
    )
    hypothesis = st.text_area(
        "가설", height=100,
        placeholder="예) 객실 등급(Pclass)이 생존에 미치는 영향이 크다.",
    )
    metric = st.text_input(
        "평가산식 (metric)", placeholder="예) accuracy",
    )
```

(d) `render`의 버튼 블록에서 `build_pipeline_input(...)` 호출 인자 교체:
```python
        inp = build_pipeline_input(
            csv_path=csv_path, loop_count=int(loop_count),
            target_column=target_column, task_type=task_type,
            description=description, hypothesis=hypothesis, metric=metric,
        )
```

- [ ] **Step 4: 통과 확인 + 전체 회귀**

Run: `python -m pytest tests/test_input_form.py -q`
Expected: PASS (4 passed).
Run: `python -m pytest -q`
Expected: 전체 통과.
Run: `python -c "import ui.input_form; import app; print('import ok')"`
Expected: `import ok`.

- [ ] **Step 5: Commit**
```bash
git add ui/input_form.py tests/test_input_form.py
git commit -m "feat: split input into data-card(column desc)/hypothesis/metric fields"
```

---

## Task 3: E2E 시각 확인

**Files:** (없음 — 검증)

- [ ] **Step 1: 앱 실행**

`.claude/launch.json`의 `streamlit-ui`로 앱을 띄우고(또는 `streamlit run app.py`), 샘플
CSV(`sample_data/sample.csv`) 업로드 후 확인:
- **데이터 카드** 칸이 업로드 컬럼으로 자동 채워짐:
  `PassengerId : \nPclass : \nSex : \nAge : \nFare : \nSurvived : ` (각 컬럼 한 줄)
- **가설**, **평가산식**이 별도 칸으로 분리됨
- 컬럼 설명을 채우고 가설/평가산식 입력 → 분석 실행 → 진행/결과 정상
- 결과 리포트에 가설과 평가산식이 표시됨

(각 화면 스크린샷 캡처)

- [ ] **Step 2: 회귀 최종 확인**

Run: `python -m pytest -q`
Expected: 전체 통과.

---

## 자체 점검 결과

- **스펙 커버리지**: 계약 rename+metric(Task1=§2), 입력 폼 3칸+컬럼 템플릿(Task2=§3), 파급
  반영(Task1: schema/mock/tests = §4), 테스트(Task1·2=§5), E2E(Task3). 데이터 카드 의미 변경은
  Task2의 템플릿/라벨로 반영.
- **플레이스홀더**: 없음(모든 코드·명령·기대출력 명시).
- **타입 일관성**: `PipelineInput(hypothesis, metric=...)`(Task1) ↔ `build_pipeline_input(...,
  hypothesis, metric="")`(Task2) ↔ schema 키 `hypothesis`/`metric`(Task1) 일관. `column_template`
  (Task2) 시그니처·반환 일관.
- **주의**: 로컬엔 validation.py·data_layer_backend.py가 없어 해당 파일 변경은 본 계획 범위 밖
  (통합 브랜치 전파 시 별도 반영 — adapter `_build_result`의 hypothesis, validation의 hypothesis).
