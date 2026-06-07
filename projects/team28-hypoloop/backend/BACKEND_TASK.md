# Hypo Loop — 백엔드 작업 지시서

> 이 문서는 백엔드 구현을 AI(Claude 등)에게 맡길 때 사용하는 지시서입니다.
> 작업 전 이 문서를 먼저 읽고, 불명확한 부분은 추측하지 말고 질문하세요.

---

## 0. 프로젝트 개요

**Hypo Loop**는 사용자가 등록한 "가설"을 ML 실험으로 자동 검증하는 Auto Research Agent 플랫폼이다.
백엔드는 **데이터 계층 관리 + YML 파일 생성 + 트리거**를 담당한다. 실제 ML 학습은 별도 에이전트(AI 팀)가 수행한다.

전체 데이터 계층:

```
u_id (사용자)
└── project_id (프로젝트)
    ├── 프로젝트 로컬 db (SQLite)
    └── 가설_id (가설)
        ├── u_id_가설_id.yml   ← 백엔드가 생성
        └── exp_id (실험)
            ├── exp_id.yml      ← 에이전트(AI팀)가 생성 (실험 설계)
            ├── status.yml      ← 실험 상태/점수 (파일로 관리, 에이전트가 갱신)
            └── 에이전트가 생성한 학습용 기능코드  ← 에이전트 영역
```

---

## 1. 백엔드 책임 범위 (Scope)

### 담당 O
- `u_id / project_id / 가설_id / exp_id` 식별자 계층 관리
- 프로젝트별 로컬 SQLite DB 생성·연결·경로 정규화
- YML 파일 생성
  - `u_id_가설_id.yml` : 가설 메타데이터 (백엔드 전용 생성 대상)
- **트리거**: 가설 yml 생성이 끝나면 에이전트의 엔드포인트를 **직접 API 호출**하여 실험 시작을 알린다 (에이전트 엔드포인트는 정우님이 구현, 호출 방법은 구현 후 공유 예정)
- DB 저장 항목 (가설 단위 메타만 DB에 보관)
  - 가설 내용
  - 실험 횟수 (병렬 횟수, 최대 길이 제한)
- 실험 상태/점수는 **DB 테이블이 아니라 `exp_id` 폴더의 상태 파일(`status.yml`)로 관리**
  - 실험 상태(ready / running / done / failed)
  - 실험별 점수 (초기엔 비어있음, 에이전트가 채움)
  - 실험 결과 분석 텍스트 (에이전트가 채움)
- 보고서용 데이터 제공 API
  - 가설별 최고점
  - 가설별 실험 그래프용 데이터 (실험별 점수 추이)
  - 실험 결과 분석 텍스트(상태 파일에서 읽어 전달)

### 담당 X (경계)
- 실제 ML 트레인 코드 작성 → **에이전트(AI 팀)**
- `exp_id.yml` (실험 설계 명세) 생성 → **에이전트(AI 팀)**
- 실험 설계 내용(피처/하이퍼파라미터/모델/수식) 산출 → 에이전트
- eda / 재실험 분기 로직 → 에이전트
- `parallel_count` 만큼의 **실험 병렬 실행/스케줄링 → 에이전트(AI 팀)** (백엔드는 숫자만 전달)
- 프론트엔드 화면 → **프론트 담당**

> ⚠️ 경계가 모호한 작업(예: yml 스키마 필드 추가)은 임의 결정하지 말고 팀 질문으로 남길 것.

---

## 2. 기술 스택

- 언어: Python 3.11+
- 웹 프레임워크: FastAPI
- DB: SQLite (프로젝트별 분리, 파일 기반)
- ORM/드라이버: **SQLAlchemy** (확정 — 가설↔실험 관계 및 스키마 확장 대비)
- 파일 포맷: YAML (PyYAML)

---

## 3. 디렉토리 구조 (백엔드)

```
backend/
├── app/
│   ├── main.py                 # FastAPI 엔트리포인트
│   ├── api/
│   │   ├── projects.py         # 프로젝트 CRUD
│   │   ├── hypotheses.py       # 가설 CRUD
│   │   └── experiments.py      # 실험(exp) CRUD
│   ├── services/
│   │   ├── yml_generator.py    # u_id_가설_id.yml / status.yml 생성 (exp_id.yml은 에이전트)
│   │   ├── trigger.py          # 가설 yml 완성 후 에이전트 엔드포인트 직접 호출
│   │   └── report_builder.py   # 최고점 / 그래프 데이터 / 분석 텍스트 집계
│   ├── db/
│   │   ├── models.py           # 스키마 정의
│   │   ├── crud.py             # DB 입출력
│   │   └── session.py          # 프로젝트별 DB 연결 관리
│   └── core/
│       └── path_utils.py       # DB/파일 경로 정규화
└── requirements.txt
```

---

## 4. DB 스키마 (초안)

> 아래는 이미지 기반 초안. 확정 전 팀 리뷰 필요.
> **실험(experiments)은 DB 테이블로 두지 않고 파일로 관리한다** (5번 참고).
> DB에는 가설 단위 메타만 보관한다.

**hypotheses**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| 가설_id | TEXT (PK) | 가설 식별자 |
| project_id | TEXT (FK) | 소속 프로젝트 |
| u_id | TEXT | 작성 사용자 |
| content | TEXT | 가설 내용 |
| max_experiments | INTEGER | 실험 최대 횟수(길이 제한) |
| parallel_count | INTEGER | 병렬 실험 횟수 |
| created_at | DATETIME | 생성 시각 |

> 실험 상태·점수·분석 텍스트는 테이블 컬럼이 아니라 각 `exp_id` 폴더의
> `status.yml` 파일에 저장되며, 실험이 진행되는 동안 계속 갱신된다.

---

## 5. YML 파일 스펙

### `u_id_가설_id.yml` (가설 메타 — **백엔드가 생성**)
```yaml
u_id: <string>
project_id: <string>
hypothesis_id: <string>
content: <가설 내용>
max_experiments: <int>      # 최대 길이 제한
parallel_count: <int>       # 병렬 횟수
ready: false                # 트리거가 true로 변경
```

### `exp_id.yml` (실험 설계 — **벡엔드와 에이전트(AI팀)가 생성**, 참고용)
> 백엔드는 이 파일을 만든다. 아래는 에이전트가 만들 산출물 형태를
> hypothesis_id, exp_id는 백엔드가 작업한다.
```yaml
  hypothesis_id: string       # 부모 가설 ID **벡엔드가 생성**
  exp_id: string              # 해당 실험 고유 ID **벡엔드가 생성** 
  design:
    experiment_text: string   # 가설 기반 실험 설계 요약 (예: "XGBoost가 더 잘될 것 같아 모델을 XGBoost로 변경하여 실험 진행")
    model: string             # 구체적인 모델명 (예: "XGBoost")
    features: list            # 사용할 피처 목록
    hyperparameters: object   # 하이퍼파라미터 키-값
    formula: string           # 평가 산식/수식 (필요 없거나 고정이면 제외 가능)
  score: float | null         # 실험 점수 (초기 null, 에이전트가 최종 채움)
```

### `status.yml` (실험 상태/점수 — **파일로 관리**)
> 실험이 진행되는 동안 계속 갱신되는 파일. DB 테이블 대신 이 파일로 상태를 추적한다.
> 백엔드는 초기 골격(hypothesis_id: string, exp_id: string)을 만들고 나머지는 진행 중 점수·상태·분석은 에이전트가 갱신한다.
> 보고서 생성 시 백엔드는 이 파일을 읽어 집계한다.
```yaml
hypothesis_id: string       # 구분자 백 
exp_id: string              # 구분자 백 
current_task: string        # 현재 진행 중인 작업 (예: "EDA 진행 중", "피처 엔지니어링 진행 중")에이전트 
status: string              # 해당 작업의 상태 (ready / running / done / failed) 에이전트 
last_updated: string        # 상태가 마지막으로 변경된 시간 에이전트 
nalysis_text: string | null # 작업 관련 로그 또는 분석 코멘트 (필요시 사용) 에이전트

```


---

## 6. 주요 API 엔드포인트 (초안)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/projects` | 프로젝트 생성 + 로컬 DB 초기화 |
| POST | `/projects/{project_id}/hypotheses` | 가설 등록 → `u_id_가설_id.yml` 생성 |
| POST | `/hypotheses/{가설_id}/ready` | 가설 yml 완성 표시 → 에이전트 엔드포인트 직접 호출 |
| POST | `/hypotheses/{가설_id}/experiments` | exp 생성 (폴더 + `status.yml` 골격 생성, status=ready) |
| GET | `/experiments/{exp_id}/status` | `status.yml` 읽어서 현재 상태/점수 반환 |
| GET | `/hypotheses/{가설_id}/report` | 하위 exp들의 `status.yml`을 모아 최고점/그래프/분석 집계 |

---

## 7. 작업 규칙 (AI에게 주는 지시)

1. **이 문서의 Scope를 벗어나는 작업은 하지 말 것.** 특히 ML 학습/실험 설계 로직은 건드리지 않는다.
2. 스키마·API 경로·필드명은 위 초안을 따르되, **추가·변경이 필요하면 코드로 밀어붙이지 말고 질문**한다.
3. 모든 함수에 타입 힌트와 docstring을 단다.
4. DB 경로는 반드시 `path_utils.py`를 통해 정규화한다(직접 문자열 결합 금지).
5. YML 생성/수정은 `yml_generator.py`에 모은다. 다른 모듈에서 직접 yaml.dump 하지 않는다. **단, `exp_id.yml`은 에이전트 산출물이므로 백엔드는 읽기만 하고 절대 생성·수정하지 않는다.** `status.yml`은 백엔드가 골격(status=ready)을 만들고, 이후 점수·상태·분석은 에이전트가 갱신한다.
6. 실험 상태/점수는 DB 테이블이 아니라 `status.yml` 파일로 관리한다. experiments 테이블을 만들지 않는다.
7. 커밋은 작은 단위로, 기능별로 나눈다. (`feat:`, `fix:`, `chore:` 컨벤션)
8. main 직접 push 대신 feature 브랜치 + PR로 올린다.

---

## 8. 우선순위 (구현 순서 제안)

1. `db/session.py` + `core/path_utils.py` — DB 연결·경로 기반 다지기
2. `db/models.py` + `db/crud.py` — hypotheses 스키마와 입출력
3. `services/yml_generator.py` — `u_id_가설_id.yml` / `status.yml` 골격 생성
4. `api/projects.py`, `api/hypotheses.py` — 등록 플로우
5. `services/trigger.py` — ready 트리거
6. `api/experiments.py` — exp 폴더/`status.yml` 생성 + 상태 조회
7. `services/report_builder.py` + `/report` — `status.yml`들을 모아 보고서 데이터 집계

---

## 9. 결정 사항 (Decisions)

> 아래 항목은 팀에서 확정 완료. 변경 시 팀 합의 필요.

- [x] ~~ORM은 SQLAlchemy vs sqlite3~~ → **SQLAlchemy로 결정**
- [x] ~~트리거 방식~~ → **직접 API 호출**로 결정 (에이전트 엔드포인트는 정우님이 구현, 트리거 방법 추후 공유)
- [x] ~~`parallel_count` 병렬 실행 주체~~ → **에이전트(AI팀)가 담당으로 결정**
- [x] ~~에이전트가 점수/분석을 돌려주는 방식~~ → **`status.yml` 파일 갱신으로 결정**
- [x] ~~`status.yml` 동시 쓰기 충돌 처리~~ → **실험별 파일 분리**로 결정 (병렬 실험은 각자 `exp_id` 폴더의 `status.yml`만 사용 → 단일 writer)
- [x] ~~프로젝트별 DB/파일 저장 경로 루트~~ → **저장소 기준 상대경로 `data/projects/{project_id}/` 고정** (로컬 실행 전제)