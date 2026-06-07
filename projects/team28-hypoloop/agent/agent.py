# agent.py
import os
from langgraph.prebuilt import create_react_agent
from langchain_upstage import ChatUpstage
from tool import tools

# Ensure LANGCHAIN_TRACING_V2 is set for LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "hypoloop_agent"

# Initialize model (Requires UPSTAGE_API_KEY environment variable)
model = ChatUpstage()

# Create the agent using LangGraph
agent_executor = create_react_agent(model, tools)

if __name__ == "__main__":
    # Example usage
    inputs = {"messages": [("user", "Hello! What can you do?")]}
    for chunk in agent_executor.stream(inputs, stream_mode="values"):
        chunk["messages"][-1].pretty_print()
