# 입력 폼 분리 + 데이터 카드 컬럼 설명 — 설계서

작성일: 2026-06-05
담당: 정의찬 (UI / 프론트)
프로젝트: 28조 ML 자동화 에이전트 (hypoloop)

## 1. 목적

입력 폼의 두 가지 불편을 고친다.

1. **가설과 평가산식이 한 칸**(`llm_instruction`)에 섞여 있어 입력이 불편 → **두 칸으로 분리**.
2. **데이터 카드**가 "데이터셋 한 줄 설명"으로 잘못 구현됨 → **각 컬럼별 설명(데이터 사전)** 입력으로 변경.
   예시(사용자 의도):
   ```
   Survived : 생존 여부 (0 = 사망, 1 = 생존)
   Pclass : 티켓 클래스 (1 = 1등석, 2 = 2등석, 3 = 3등석)
   Sex : 성별
   ...
   ```

## 2. 계약 변경 (`backend/interface.py`)

`PipelineInput`을 다음과 같이 바꾼다.

- `llm_instruction: str` → **`hypothesis: str`** 로 이름 변경 (의미: 사용자 가설). 동작·검증은 동일
  (값이 가설 하나로 좁혀짐).
- **`metric: str = ""`** 필드 신규 추가 (평가산식, 자유 텍스트). 하위호환 위해 기본값 `""`.
- `DataCard.description: str` — 필드명·타입 유지하되, **의미를 "컬럼별 설명(데이터 사전)"** 으로 사용.
  (구조 변경 없음 — 줄바꿈으로 구분된 `컬럼명 : 설명` 텍스트를 담는다.)

> 이름 변경(`llm_instruction`→`hypothesis`)은 계약 전반에 영향: validation, mock/adapter 리포트,
> api/schema, 테스트를 일괄 갱신한다. `metric`은 기본값이 있어 기존 코드 비파괴.

## 3. 입력 폼 (`ui/input_form.py`)

한 칸이던 입력을 셋으로 분리한다(순서: 데이터 카드 → 가설 → 평가산식).

### 3.1 데이터 카드 (컬럼 설명)
- 단일 `st.text_area`.
- **CSV 업로드 시 컬럼명으로 템플릿 자동 채움**: 업로드된 df의 각 컬럼을
  `f"{col} : "` 한 줄씩으로 미리 깔아 `value`/`placeholder`로 제공 → 사용자는 설명만 채움.
  - 구현: 순수 헬퍼 `column_template(columns: list[str]) -> str` 가
    `"Survived : \nPclass : \n..."` 를 반환. 단위 테스트 대상.
  - text_area의 `value`를 세션 상태로 관리(업로드 컬럼이 바뀌면 템플릿 갱신, 사용자가 채운 내용은
    같은 파일이면 유지).
- 결과 문자열은 `DataCard.description` 으로 전달.

### 3.2 가설 (hypothesis)
- `st.text_area`. placeholder 예: "예) 객실 등급(Pclass)이 생존에 미치는 영향이 크다."
- `PipelineInput.hypothesis` 로 전달. (검증: 비어 있으면 에러 — 기존 llm_instruction 필수와 동일)

### 3.3 평가산식 (metric)
- `st.text_input`(한 줄, 자유 텍스트). placeholder 예: "예) accuracy".
- `PipelineInput.metric` 으로 전달. (선택 입력 — 비어도 통과)

### 3.4 순수 로직
- `column_template(columns)` (위) — 테스트.
- `build_pipeline_input(...)` 시그니처에 `hypothesis`, `metric` 반영(기존 `llm_instruction` 제거,
  `description`은 컬럼 설명 문자열).

## 4. 파급 반영

- `backend/validation.py`: `inp.llm_instruction` → `inp.hypothesis` (가설 필수 검사 유지).
- `backend/mock.py` `_build_result`: 리포트의 `> {inp.llm_instruction}` → `inp.hypothesis`.
  (선택) 평가산식을 리포트에 한 줄 추가.
- `backend/data_layer_backend.py` `_build_result`: `hypothesis=inp.llm_instruction` →
  `inp.hypothesis`. (어댑터가 있는 통합 브랜치 전파 시.)
- `api/schema.py`: `input_to_dict`/`input_from_dict`에 `hypothesis`, `metric` 반영
  (기존 `llm_instruction` 제거).
- 테스트 전반: `PipelineInput(...)` 생성부의 `llm_instruction=` → `hypothesis=`, `metric` 추가 케이스.

## 5. 테스트

- **순수 로직**: `column_template`(컬럼 → 템플릿 문자열), `build_pipeline_input`(새 시그니처로
  PipelineInput 조립, hypothesis/metric/description 매핑), `infer_task_type`(변경 없음, 회귀).
- **계약/직렬화**: `PipelineInput`에 hypothesis/metric 존재 및 기본값, schema 라운드트립.
- **검증**: 가설(hypothesis) 비면 에러, 채우면 통과. 평가산식은 비어도 통과.
- **회귀**: 기존 전체 스위트 통과(이름 변경 누락 없음).

## 6. 적용 위치 / 범위

- 우선 **로컬 프론트 저장소**(`/Users/justice/Desktop/AI 교육`, 루트 레이아웃)에서 TDD 구현.
- 이후 `feat/integration`·`frontend` 브랜치로 전파(별도 단계, 사용자 승인 시).
- 데이터 카드 입력 방식은 **자유 텍스트 한 칸 + 컬럼명 템플릿 자동 채움**(구조화 per-column 폼 아님).
- 평가산식은 **자유 텍스트**(드롭다운 아님).

## 7. 제약 / 원칙

- 계약의 새 필드는 하위호환(`metric` 기본값) — 단, `llm_instruction`→`hypothesis` 이름 변경은
  같은 커밋에서 모든 사용처를 함께 갱신(빌드/테스트 깨짐 방지).
- 데이터 카드 description은 자유 형식 문자열 — 파싱·검증하지 않는다(백엔드/LLM이 해석).
