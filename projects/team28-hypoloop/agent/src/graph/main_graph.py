import os
from dotenv import load_dotenv
load_dotenv()

from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from agent.src.graph.state import AgentState
from agent.src.tool import tools

SYSTEM_PROMPT = """You are an elite, autonomous Machine Learning Agent.
Your goal is to conduct an end-to-end ML experiment and write a report.

[ENVIRONMENT & CONTEXT]
- Project ID: {project_id}
- Hypothesis ID: {hypothesis_id}
- Hypothesis Directory: {hypothesis_dir}
- Experiment Directory: {exp_dir}

[CRITICAL INSTRUCTIONS]
1. Read the path_rules template: Use `read_file` to read `shared/templates/path_rules.md` and strictly follow its directory rules and read-only DB constraints.
2. Read the code templates: Use `read_file` to read `shared/templates/eda_template.py` and `shared/templates/train_template.py` to understand the mandatory code format.
3. Read the hypothesis configuration from `data/projects/{project_id}/hypotheses/{hypothesis_id}/{u_id}_{hypothesis_id}.yml` to understand the goal.
4. Read the data description: Use `read_file` to read `data/projects/{project_id}/data_description.txt` if it exists. This file explains all columns and identifies the target variable.
5. **UPDATE STATUS**: Use the `update_status` tool to update the UI status frequently (e.g. `current_task`: "EDA 준비 중", `status`: "running"). Do this before starting each major step (EDA, Training) and when the experiment is completed (`status`: "done").

**CRITICAL INSTRUCTIONS TO PREVENT ERRORS:**
- DO NOT output tool calls as raw text or XML (e.g., `<tool_call>...</tool_call>`). You MUST use the proper JSON function calling API.
- If you need to read multiple files, do NOT call the `read_file` tool multiple times in parallel in a single turn. Call ONE tool at a time, wait for the response, and then call the next one. Otherwise, you will enter an infinite loop.
5. Data is in the SQLite DB `data/projects/{project_id}/project.db`. The main table is usually `dataset`. **CRITICAL**: Do NOT use `read_file` to read the DB. Use `execute_command` with a proper SQL query (e.g., `sqlite3 {project_id}/project.db "SELECT * FROM dataset LIMIT 5;"`) or write a short Python script to inspect it.
6. Write your EDA code to `{exp_dir}/eda.py` and execute it. Make sure images are saved to `{exp_dir}/img/`.
7. Write your Train code to `{exp_dir}/train.py` and execute it. Make sure MLflow logs correctly.
   **CRITICAL**: You MUST set the MLflow tracking URI to `sqlite:///{hypothesis_dir}/mlflow.db` so that all experiments for this hypothesis share the same database.
8. Finally, write a comprehensive experiment report to `{exp_dir}/report.md` summarizing the EDA findings, the model training results (Accuracy/Score), and whether the hypothesis was supported.
   **CRITICAL**: When embedding images in `report.md`, you MUST use relative paths (e.g., `![caption](img/target_distribution.png)`). Do NOT use absolute paths.
   **CRITICAL**: After writing the report, call `update_status` with `status: "done"`, `current_task: "실험 완료"`, a brief `analysis_text`, and the numeric `score` (e.g., your R2 Score or RMSE) to record the experiment result.

Remember to execute the python scripts using `execute_command` to verify they work and generate the expected artifacts.
"""

# Initialize Solar LLM
llm = ChatUpstage(model="solar-pro")
llm_with_tools = llm.bind_tools(tools)

def agent_node(state: AgentState):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    chain = prompt | llm_with_tools
    
    # Fill system prompt with state variables
    res = chain.invoke({
        "project_id": state["project_id"],
        "u_id": state.get("u_id", "demo_user"),
        "hypothesis_id": state["hypothesis_id"],
        "hypothesis_dir": state["hypothesis_dir"],
        "exp_dir": state["exp_dir"],
        "messages": state["messages"]
    })
    
    return {"messages": [res]}

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent_node)
    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

# For LangGraph Studio compatibility
graph = build_graph()
