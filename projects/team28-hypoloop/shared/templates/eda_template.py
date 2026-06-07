import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ==========================================
# [AGENT REQUIREMENT] 
# 1. DB_PATH는 프로젝트 루트를 기준으로 동적 또는 절대 경로로 할당할 것
# 2. DB 연결 시 반드시 '?mode=ro' & uri=True 를 사용할 것 (Read-Only)
# 3. 모든 생성된 시각화 차트 이미지는 반드시 IMG_DIR 에 저장할 것
# ==========================================

DB_PATH = "data/projects/{project_id}/project.db" # 실제 경로로 교체 필요
EXP_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(EXP_DIR, "img")

# img 폴더 강제 생성
os.makedirs(IMG_DIR, exist_ok=True)

def load_data():
    """SQLite Database (Read-Only) 연동"""
    db_abs_path = os.path.abspath(DB_PATH)
    conn_uri = f"file:{db_abs_path}?mode=ro"
    
    with sqlite3.connect(conn_uri, uri=True) as conn:
        df = pd.read_sql("SELECT * FROM dataset", conn)
        # data_card 도 함께 로드하여 활용 가능
        # card_df = pd.read_sql("SELECT * FROM data_card", conn)
    return df

def run_eda():
    df = load_data()
    
    # ---------------------------------------------------------
    # 에이전트는 여기에 실제 EDA 및 시각화 코드를 작성합니다.
    # ---------------------------------------------------------
    
    plt.figure(figsize=(10, 6))
    # sns.histplot(df['TargetColumn'], kde=True)
    plt.title("Example Distribution")
    
    # 이미지 저장 (반드시 IMG_DIR 하위에 저장)
    save_path = os.path.join(IMG_DIR, "example_distribution.png")
    plt.savefig(save_path)
    plt.close()
    
    print(f"[*] EDA 완료. 차트 이미지가 {IMG_DIR} 에 저장되었습니다.")

if __name__ == "__main__":
    run_eda()
