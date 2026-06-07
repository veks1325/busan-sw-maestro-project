import argparse
import os
import uuid
import sys
import yaml
import time
from dotenv import load_dotenv
load_dotenv()
from langchain_core.messages import HumanMessage
from agent.src.graph.main_graph import build_graph

class Tee(object):
    def __init__(self, name, mode, stream):
        self.file = open(name, mode)
        self.stream = stream
        
    def write(self, data):
        self.file.write(data)
        self.file.flush()
        self.stream.write(data)
        self.stream.flush()
        
    def flush(self):
        self.file.flush()
        self.stream.flush()
from agent.src.graph.main_graph import build_graph

def main():
    parser = argparse.ArgumentParser(description="Agent Trigger Script")
    parser.add_argument("--trigger_id", type=str, default="1", help="트리거 고유 ID")
    parser.add_argument("--project_id", type=str, required=True, help="대상 프로젝트 ID")
    parser.add_argument("--hypothesis_id", type=str, required=True, help="대상 가설 ID")
    parser.add_argument("--u_id", type=str, default="demo_user", help="사용자 ID")
    
    args = parser.parse_args()
    
    # Generate unique experiment ID
    exp_id = f"exp_{uuid.uuid4().hex[:6]}"
    
    print(f"[*] Agent Started with Trigger ID: {args.trigger_id}")
    print(f"[*] Target Project ID: {args.project_id}")
    print(f"[*] Target Hypothesis ID: {args.hypothesis_id}")
    print(f"[*] Generated Experiment ID: {exp_id}")
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    hypothesis_dir = os.path.join(base_dir, "data", "projects", args.project_id, "hypotheses", args.hypothesis_id)
    
    # 1. Ensure hypothesis directory exists
    os.makedirs(hypothesis_dir, exist_ok=True)
    
    # 2. Ensure hypothesis YAML file exists (Create a dummy one if it doesn't)
    hypothesis_file = os.path.join(hypothesis_dir, f"{args.u_id}_{args.hypothesis_id}.yml")
    if not os.path.exists(hypothesis_file):
        print(f"[*] Creating dummy hypothesis file: {hypothesis_file}")
        dummy_hyp = {
            "hypothesis_id": args.hypothesis_id,
            "design": {
                "experiment_text": "Target variable 'SalePrice'에 대한 기초 통계량 분포를 EDA하고, 누락된 값 처리 후 RandomForestRegressor 모델을 학습하여 검증하라.",
                "model": "RandomForestRegressor",
                "features": ["OverallQual", "GrLivArea", "GarageCars", "TotalBsmtSF"],
                "hyperparameters": {"n_estimators": 100, "random_state": 42}
            }
        }
        with open(hypothesis_file, "w") as f:
            yaml.dump(dummy_hyp, f)
            
    # 3. Create the experiment directory
    exp_dir = os.path.join(hypothesis_dir, "experiments", exp_id)
    os.makedirs(exp_dir, exist_ok=True)
    
    # Setup File Logging
    log_file = os.path.join(exp_dir, "agent.log")
    sys.stdout = Tee(log_file, "a", sys.stdout)
    sys.stderr = Tee(log_file, "a", sys.stderr)
    
    print(f"[*] Target Experiment Directory created: {exp_dir}")
    
    # 4. Build and Run the Graph
    print("[*] Building LangGraph Workflow...")
    graph = build_graph()
    
    state = {
        "messages": [HumanMessage(content="Please start the ML experiment: read templates, generate and run EDA code, generate and run Train code, and finally write the report.md.")],
        "project_id": args.project_id,
        "u_id": args.u_id,
        "hypothesis_id": args.hypothesis_id,
        "hypothesis_dir": hypothesis_dir,
        "exp_dir": exp_dir
    }
    
    print("[*] Starting Agent Execution Loop...")
    for event in graph.stream(state, {"recursion_limit": 50}):
        time.sleep(10)  # 데모 영상 촬영과 API Rate Limit 방지를 위해 10초 딜레이
        for key, value in event.items():
            if "messages" in value:
                msg = value["messages"][-1]
                msg_type = type(msg).__name__
                reasoning = msg.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    print(f"\n>>> [{key.upper()}] ({msg_type} - 🤔 REASONING)")
                    print(f"    {reasoning[:300].replace(chr(10), ' ')} ...")
                
                content_preview = msg.content[:300].replace('\n', ' ')
                if content_preview:
                    print(f"\n>>> [{key.upper()}] ({msg_type})")
                    print(f"    {content_preview} ...\n")
            else:
                print(f"[{key}]: {value}")
                
    print("[*] Agent Loop Completed.")

if __name__ == "__main__":
    main()
