# Agent Path and Authorization Rules

에이전트는 코드를 생성하고 파일을 저장할 때 반드시 아래의 절대 규칙을 따라야 합니다.

## 1. Directory Structure Constraints (경로 규칙)
프로젝트 입력 데이터는 프로젝트 디렉터리에 아래 고정 파일명으로 저장됩니다:
- 학습 데이터: `data/projects/{project_id}/train.csv`
- 테스트 데이터: `data/projects/{project_id}/test.csv`
- 데이터 설명: `data/projects/{project_id}/data_description.txt`
- 백엔드 메타데이터: `data/projects/{project_id}/project.db` (에이전트 학습 입력으로 사용 금지)

모든 작업은 주어진 실험(Experiment) 디렉터리 하위에서만 이루어져야 합니다.
**기본 경로 형식**: `data/projects/{project_id}/hypotheses/{hypothesis_id}/experiments/{exp_id}/`

에이전트가 코드를 짤 때 다음 파일/폴더 명칭을 강제합니다:
- **EDA 코드**: `{exp_id}/eda.py`
- **시각화 이미지**: 반드시 `{exp_id}/img/` 디렉터리 내부에 생성 (예: `target_dist.png`)
- **학습(Train) 코드**: `{exp_id}/train.py`
- **실험 리포트**: `{exp_id}/report.md`

## 2. Authorization Constraints (권한 및 보안 규칙)
1. **프로젝트 외부 접근 금지**: 에이전트는 프로젝트 상위 디렉터리나 관계없는 시스템 경로에 대해 파일 쓰기/수정/삭제를 수행해서는 안 됩니다.
2. **CSV 직접 로딩**: EDA와 학습 데이터는 `train.csv`, `test.csv`를 `pandas.read_csv`로 직접 읽습니다. SQL을 생성하거나 `project.db`를 모델 데이터 소스로 사용하지 마십시오.
3. **백엔드 DB 접근 금지**: `project.db`는 프로젝트와 데이터 카드 등의 백엔드 메타데이터 전용입니다. 에이전트 코드는 이 파일을 읽거나 수정하지 않습니다.
