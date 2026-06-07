import os
import sqlite3
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
# TODO: 에이전트는 사용할 모델을 추가로 import 하세요. (예: RandomForestRegressor)

# ==========================================
# [AGENT REQUIREMENT] 
# 1. DB_PATH는 프로젝트 루트를 기준으로 동적/절대 경로로 할당할 것
# 2. DB 연결 시 반드시 '?mode=ro' & uri=True 를 사용할 것 (Read-Only)
# 3. 모델 학습 결과와 메트릭은 반드시 MLflow로 로깅할 것
# ==========================================

DB_PATH = "data/projects/{project_id}/project.db" # 실제 경로로 교체 필요
MLFLOW_URI = "sqlite:///{hypothesis_dir}/mlflow.db" # 모든 가설 내 실험이 공유하는 DB
EXP_NAME = "exp_{project_id}"

def load_data():
    """SQLite Database (Read-Only) 연동"""
    db_abs_path = os.path.abspath(DB_PATH)
    conn_uri = f"file:{db_abs_path}?mode=ro"
    
    with sqlite3.connect(conn_uri, uri=True) as conn:
        df = pd.read_sql("SELECT * FROM dataset", conn)
    return df

def run_training():
    df = load_data()
    
    # ---------------------------------------------------------
    # 에이전트는 여기에 실제 데이터 전처리 및 피처 엔지니어링 코드를 작성합니다.
    # ---------------------------------------------------------
    # 예시: X, y 분리 및 분할
    # X = df.drop(columns=["TargetColumn"])
    # y = df["TargetColumn"]
    # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # MLflow 설정
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXP_NAME)
    
    with mlflow.start_run():
        # ---------------------------------------------------------
        # 에이전트는 여기에 모델 초기화, 학습, 평가 코드를 작성합니다.
        # ---------------------------------------------------------
        # model = RandomForestRegressor()
        # model.fit(X_train, y_train)
        # score = model.score(X_test, y_test)
        
        # MLflow 파라미터 및 메트릭 기록 (반드시 수행)
        # mlflow.log_param("model_type", "RandomForest")
        # mlflow.log_metric("r2_score", score)
        # mlflow.sklearn.log_model(model, "model")
        pass
        
    print("[*] Training 및 MLflow 로깅이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    run_training()
