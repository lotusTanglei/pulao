import operator
from typing import Annotated, TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from src.tools import registry

# 1. Define AgentState
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

def create_langchain_tools() -> List[StructuredTool]:
    """Convert Pulao tools to LangChain StructuredTools."""
    tools = []
    # registry._tools maps name to function
    # access protected member _tools as per user instruction
    for name, func in registry._tools.items():
        # StructuredTool.from_function automatically infers schema from signature and docstring
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=func.__doc__ or f"Tool {name}",
        )
        tools.append(tool)
    return tools

def create_agent_app(config: Dict[str, Any]):
    """
    Create and compile the LangGraph agent.
    
    Args:
        config: Configuration dictionary containing:
            - api_key: OpenAI API key
            - base_url: OpenAI API base URL
            - model: Model name (e.g., "gpt-4o")
            
    Returns:
        Compiled LangGraph application.
    """
    # Initialize tools
    tools = create_langchain_tools()
    tool_node = ToolNode(tools)
    
    # Initialize model
    model = ChatOpenAI(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model", "gpt-4o"),
        temperature=0,
    ).bind_tools(tools)
    
    # Define the call_model node
    def call_model(state: AgentState):
        messages = state["messages"]
        response = model.invoke(messages)
        return {"messages": [response]}
        
    # Define the conditional edge logic
    def should_continue(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # Build the graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    workflow.add_edge(START, "agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        ["tools", END]
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()
