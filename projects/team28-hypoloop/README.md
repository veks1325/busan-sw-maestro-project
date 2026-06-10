# Hypo Loop

> 사용자가 등록한 가설을 AI 에이전트가 ML 실험으로 설계하고 검증하여, 점수와 분석 보고서를 제공하는 Auto Research Agent 플랫폼

Busan SW Maestro Project **Team 28**의 최종 프로젝트입니다.

## 프로젝트 소개

데이터 기반 가설을 검증하려면 실험 설계, EDA, 모델 학습, 평가, 결과 정리까지 반복적인 작업이 필요합니다. Hypo Loop는 이 과정을 LangGraph 기반 에이전트로 연결하여 사용자가 가설과 데이터만 등록하면 여러 실험을 병렬로 수행하고 결과를 보고서로 확인할 수 있게 합니다.

### 주요 기능

- 프로젝트별 학습 데이터, 테스트 데이터, 데이터 설명 관리
- 검증할 가설과 최대 실험 수, 병렬 실행 수 등록
- `실험 설계 -> EDA -> 학습/평가 -> 보고서` 단계별 에이전트 실행
- 서로 다른 실험 전략을 병렬로 수행하고 상태와 점수를 실시간 추적
- 가설별 최고 점수, 점수 추이, EDA 이미지, 분석 보고서 제공
- 프로젝트별 SQLite와 YML 기반 실험 산출물 분리 저장

## 동작 흐름

```mermaid
flowchart LR
    A[프로젝트 생성] --> B[CSV 및 데이터 설명 등록]
    B --> C[가설 등록]
    C --> D[실험 골격 생성]
    D --> E[LangGraph 에이전트 실행]
    E --> F[실험 설계]
    F --> G[EDA]
    G --> H[학습 및 평가]
    H --> I[보고서 생성]
    I --> J[대시보드 결과 확인]
```

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | Streamlit, Plotly, Pandas |
| Backend | FastAPI, SQLAlchemy, SQLite, Pydantic |
| AI Agent | LangGraph, LangChain, Upstage Solar |
| ML / Experiment | scikit-learn, MLflow, Matplotlib, Seaborn |
| Data / State | CSV, YAML, SQLite |
| Test | Pytest, HTTPX |

## 프로젝트 구조

```text
team28-hypoloop/
├── agent/                  # 실험 설계·EDA·학습·보고서 에이전트
│   ├── src/graph/          # 단계별 LangGraph 워크플로
│   ├── src/runner.py       # 병렬 실험 실행기
│   └── tests/
├── backend/                # FastAPI API 및 데이터 계층
│   ├── app/api/            # 프로젝트·데이터·가설·실험 API
│   ├── app/services/       # YML 생성, 트리거, 보고서 집계
│   └── tests/
├── frontend/               # Streamlit 사용자 화면
│   ├── src/pages/
│   ├── src/components/
│   ├── src/api/
│   └── tests/
├── shared/                 # 공통 YML 스키마와 코드 템플릿
├── data/projects/          # 프로젝트별 런타임 데이터(실행 시 생성)
└── .env.example            # 환경변수 예시
```

프로젝트 데이터는 다음 계층으로 관리합니다.

```text
data/projects/{project_id}/
├── project.db
├── train.csv
├── test.csv
├── data_description.txt
└── hypotheses/{hypothesis_id}/
    ├── {u_id}_{hypothesis_id}.yml
    └── experiments/{exp_id}/
        ├── {exp_id}.yml
        ├── status.yml
        ├── eda.py
        ├── train.py
        ├── report.md
        └── img/
```

## 실행 방법

### 1. 환경 준비

Python 3.10 이상을 권장합니다. 백엔드가 같은 Python 환경의 에이전트를 실행하므로 루트에서 모든 의존성을 함께 설치합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r agent/requirements.txt
pip install -r frontend/requirements.txt
```

환경변수 파일을 준비하고 사용할 LLM API 키를 입력합니다.

```bash
cp .env.example .env
```

```dotenv
UPSTAGE_API_KEY=your_api_key
HYPOLOOP_DATA_ROOT=data
HYPOLOOP_BACKEND_URL=http://localhost:8000
```

`HYPOLOOP_DATA_ROOT`를 생략하면 저장소의 `data/` 디렉터리를 사용합니다.

### 2. 백엔드 실행

저장소 루트에서 실행합니다.

```bash
PYTHONPATH=backend:. uvicorn backend.app.main:app --reload --port 8000
```

- API 문서: <http://localhost:8000/docs>
- 가설 실행 요청이 들어오면 백엔드가 에이전트 runner를 백그라운드 프로세스로 시작합니다.

### 3. 프론트엔드 실행

새 터미널에서 실행합니다.

```bash
source .venv/bin/activate
cd frontend
streamlit run app.py
```

브라우저에서 <http://localhost:8501>에 접속한 뒤 다음 순서로 사용할 수 있습니다.

1. 프로젝트 생성
2. `train.csv`, `test.csv`, 데이터 설명 파일 등록
3. 가설, 최대 실험 수, 병렬 실행 수 입력
4. 에이전트 진행 상태 확인
5. 완료된 실험 점수와 보고서 확인

### API 키 없이 UI 확인

백엔드와 에이전트 없이 프론트엔드의 예시 흐름만 확인할 수 있습니다.

```bash
cd frontend
HYPOLOOP_STORE=mock streamlit run app.py
```

## 테스트

저장소 루트와 동일한 가상환경에서 실행합니다.

```bash
PYTHONPATH=. pytest -q agent/tests
PYTHONPATH=backend:. pytest -q backend/tests
PYTHONPATH=frontend pytest -q frontend/tests
```

## 역할 분담

- **Frontend**: 프로젝트·가설 등록 UI, 에이전트 진행 상태, 결과 대시보드와 보고서
- **Backend**: 식별자와 파일 경로 관리, 프로젝트별 SQLite, YML 골격 생성, 에이전트 트리거, 보고서 데이터 집계
- **AI Agent**: 실험 설계, EDA, 학습 코드 생성과 실행, 병렬 스케줄링, 점수 및 분석 결과 갱신

실험 상태와 점수는 DB 테이블이 아닌 각 실험의 `status.yml`로 관리하며, SQLite는 백엔드 메타데이터에만 사용합니다.

## 제출 정보

- 제출 팀: **Team 28**
- 제출 폴더명: `projects/team28-hypoloop`
- 프로젝트 저장소: [28-hypoloop/hypoloop](https://github.com/28-hypoloop/hypoloop)

외부 제출 저장소에는 프로젝트 내부의 `.git` 디렉터리를 제외하고 복사해야 합니다.

```bash
mkdir -p projects/team28-hypoloop
rsync -av --exclude='.git' /path/to/hypoloop/ projects/team28-hypoloop/
```
