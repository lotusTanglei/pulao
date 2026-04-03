"""
LangGraph Agent 状态机

本模块是 Pulao 的核心编排层，负责：
1. 管理 Agent 状态
2. 协调 AI 模型与工具调用
3. 集成安全框架（风险评估、人工确认、审计日志）

状态机流程:
START → agent → route → {execute, preview, deny}
                              ↓
                         preview → hitl → {tools, agent}
                              ↓
                         tools → audit → agent → END
"""

from typing import Annotated, TypedDict, List, Dict, Any, Optional
import uuid

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.tools.registry import registry
from src.core.risk_guard import RiskGuard, RiskDecision, RiskLevel
from src.core.policy_store import PolicyStore
from src.core.dry_run import DryRunExecutor, ExecutionPlan
from src.core.hitl import HITLController
from src.core.audit import AuditLogger
from src.core.confidence import ConfidenceEvaluator, ConfidenceResult
from src.core.logger import logger


# ============ 状态定义 ============

class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[List[BaseMessage], add_messages]

    # 安全框架状态
    trace_id: str                              # 全链路追踪 ID
    session_id: str                            # 会话 ID
    execution_plan: Optional[ExecutionPlan]    # 执行计划
    confirmed: bool                            # 用户是否已确认
    denied_reason: Optional[str]               # 拒绝原因
    audit_events: List[str]                    # 审计事件 ID 列表
    confidence_result: Optional[ConfidenceResult]  # 置信度评估结果


# ============ 安全组件实例 ============

_risk_guard = RiskGuard(PolicyStore())
_dry_run_executor = DryRunExecutor(_risk_guard)


def _generate_trace_id() -> str:
    """生成追踪 ID"""
    return f"trace_{uuid.uuid4().hex[:12]}"


def _generate_session_id() -> str:
    """生成会话 ID"""
    return f"sess_{uuid.uuid4().hex[:8]}"


# ============ 工具创建 ============

def create_langchain_tools() -> List[StructuredTool]:
    """创建 LangChain 工具列表"""
    tools = []
    for name, func in registry._tools.items():
        tool = StructuredTool.from_function(
            func=func,
            name=name,
            description=func.__doc__ or f"Tool {name}",
        )
        tools.append(tool)
    return tools


# ============ 节点函数 ============

def agent_node(state: AgentState, model) -> dict:
    """Agent 推理节点"""
    response = model.invoke(state["messages"])

    # 解析置信度（从 AI 文本响应中）
    confidence_result = None
    if hasattr(response, 'content') and response.content:
        confidence_result = ConfidenceEvaluator.parse_confidence(response.content)
        if confidence_result.score < 0.85:  # 只记录低于默认值的情况
            logger.info(f"AI confidence: {confidence_result.score}, reasoning: {confidence_result.reasoning[:100]}")

    return {
        "messages": [response],
        "confidence_result": confidence_result
    }


def route_node(state: AgentState) -> str:
    """
    路由决策节点

    根据风险评估决定执行路径:
    - end: 无工具调用
    - execute: 所有操作都是 ALLOW
    - preview: 有操作需要 CONFIRM
    - deny: 有操作被 DENY
    """
    last_message = state["messages"][-1]

    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return "end"

    # 评估所有工具调用
    has_confirm = False

    for tc in last_message.tool_calls:
        assessment = _risk_guard.assess(tc["name"], tc.get("args", {}))

        if assessment.decision == RiskDecision.DENY:
            return "deny"

        if assessment.decision == RiskDecision.CONFIRM:
            has_confirm = True

    if has_confirm:
        return "preview"

    return "execute"


def preview_node(state: AgentState) -> dict:
    """生成执行计划节点"""
    last_message = state["messages"][-1]

    tool_calls = [
        {"name": tc["name"], "args": tc.get("args", {}), "id": tc.get("id", "")}
        for tc in last_message.tool_calls
    ]

    plan = _dry_run_executor.generate_plan(tool_calls)

    logger.info(f"Generated execution plan: {plan.plan_id}, risk: {plan.total_risk.value}")

    return {
        "execution_plan": plan
    }


def hitl_node(state: AgentState) -> dict:
    """人工确认节点"""
    plan = state["execution_plan"]
    confidence = state.get("confidence_result")

    # 检查 DENY
    for step in plan.steps:
        if step.risk_assessment.decision == RiskDecision.DENY:
            return {
                "confirmed": False,
                "denied_reason": step.risk_assessment.reason
            }

    # 用户确认（传入置信度信息）
    approved = HITLController.confirm(plan, confidence)

    logger.info(f"HITL confirmation: {'approved' if approved else 'rejected'}")

    return {
        "confirmed": approved,
        "denied_reason": None if approved else "用户取消"
    }


def deny_node(state: AgentState) -> dict:
    """处理拒绝的操作"""
    last_message = state["messages"][-1]
    denied_tools = []

    for tc in last_message.tool_calls:
        assessment = _risk_guard.assess(tc["name"], tc.get("args", {}))
        if assessment.decision == RiskDecision.DENY:
            denied_tools.append(f"{tc['name']}: {assessment.reason}")

            # 记录审计日志
            AuditLogger.log(
                trace_id=state.get("trace_id", ""),
                session_id=state.get("session_id", ""),
                tool_name=tc["name"],
                arguments=tc.get("args", {}),
                risk_level=assessment.risk_level.value,
                decision="deny",
                confirm_state="skipped",
                result="denied",
                error_message=assessment.reason
            )

    # 返回拒绝消息
    denial_msg = f"以下操作被系统拒绝:\n" + "\n".join(f"- {t}" for t in denied_tools)
    denial_msg += "\n\n请修改你的请求或尝试其他方案。"

    logger.warning(f"Denied operations: {denied_tools}")

    return {
        "messages": [AIMessage(content=denial_msg)]
    }


def audit_node(state: AgentState) -> dict:
    """审计日志节点"""
    event_ids = []

    # 获取最后一个工具调用的结果
    last_message = state["messages"][-1]

    # 从历史中找到对应的工具调用
    for i, msg in enumerate(reversed(state["messages"][:-1])):
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                event_id = AuditLogger.log(
                    trace_id=state.get("trace_id", ""),
                    session_id=state.get("session_id", ""),
                    tool_name=tc["name"],
                    arguments=tc.get("args", {}),
                    risk_level="medium",  # 能执行到这里说明已经过确认
                    decision="confirm",
                    confirm_state="confirmed",
                    result="success"
                )
                event_ids.append(event_id)
            break

    logger.debug(f"Audit events: {event_ids}")

    return {
        "audit_events": state.get("audit_events", []) + event_ids
    }


# ============ 图构建 ============

def create_agent_app(config: Dict[str, Any]):
    """
    创建 Agent 应用

    Args:
        config: 配置字典，包含 api_key, base_url, model 等

    Returns:
        编译后的 LangGraph 应用
    """
    tools = create_langchain_tools()
    tool_node = ToolNode(tools)

    model = ChatOpenAI(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model", "gpt-4o"),
        temperature=0,
    ).bind_tools(tools)

    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", lambda state: agent_node(state, model))
    workflow.add_node("preview", preview_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("audit", audit_node)
    workflow.add_node("deny", deny_node)

    # 设置入口
    workflow.add_edge(START, "agent")

    # agent 路由
    workflow.add_conditional_edges(
        "agent",
        route_node,
        {
            "end": END,
            "execute": "tools",
            "preview": "preview",
            "deny": "deny",
        }
    )

    # preview -> hitl
    workflow.add_edge("preview", "hitl")

    # hitl 路由
    workflow.add_conditional_edges(
        "hitl",
        lambda state: "execute" if state.get("confirmed") else "reject",
        {
            "execute": "tools",
            "reject": "agent"  # 用户拒绝，返回 agent 重新规划
        }
    )

    # deny -> agent (重新规划)
    workflow.add_edge("deny", "agent")

    # tools -> audit -> agent
    workflow.add_edge("tools", "audit")
    workflow.add_edge("audit", "agent")

    return workflow.compile()
