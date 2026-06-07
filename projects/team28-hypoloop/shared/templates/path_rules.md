# Agent Path and Authorization Rules

에이전트는 코드를 생성하고 파일을 저장할 때 반드시 아래의 절대 규칙을 따라야 합니다.

## 1. Directory Structure Constraints (경로 규칙)
모든 작업은 주어진 실험(Experiment) 디렉터리 하위에서만 이루어져야 합니다.
**기본 경로 형식**: `data/projects/{project_id}/hypotheses/{hypothesis_id}/experiments/{exp_id}/`

에이전트가 코드를 짤 때 다음 파일/폴더 명칭을 강제합니다:
- **EDA 코드**: `{exp_id}/eda.py`
- **시각화 이미지**: 반드시 `{exp_id}/img/` 디렉터리 내부에 생성 (예: `target_dist.png`)
- **학습(Train) 코드**: `{exp_id}/train.py`
- **실험 리포트**: `{exp_id}/report.md`

## 2. Authorization Constraints (권한 및 보안 규칙)
1. **프로젝트 외부 접근 금지**: 에이전트는 프로젝트 상위 디렉터리나 관계없는 시스템 경로에 대해 파일 쓰기/수정/삭제를 수행해서는 안 됩니다.
2. **SQLite 데이터베이스 읽기 전용(Read-Only)**: `project.db` 파일에 접근할 때는 절대로 데이터를 덮어쓰거나 수정해서는 안 됩니다. **반드시 파이썬의 `sqlite3` 연결 시 `mode=ro` 속성과 `uri=True` 옵션을 사용**하여 읽기 권한만 갖도록 코드를 작성하십시오.
   - ✅ 올바른 예: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
   - ❌ 잘못된 예: `sqlite3.connect(db_path)` (DB 데이터 손상 위험 발생)
