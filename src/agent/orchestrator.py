"""
AI 核心处理模块

本模块是 Pulao 的大脑，负责：
1. 与 AI 大语言模型进行交互（DeepSeek/OpenAI/Azure 等）
2. 实现 ReAct Agent 循环，让 AI 能够调用工具执行实际操作
3. 处理 AI 返回的响应，提取 JSON/YAML 内容
4. 管理 AI 对话会话状态和历史记录

主要类：
    - AISession: 封装 AI 对话状态，包括历史记录和客户端配置

主要函数：
    - process_deployment(): 处理用户的部署指令
    - get_session(): 获取全局 AISession 实例
    - extract_json(): 从 AI 响应中提取 JSON 数据
    - clean_yaml_content(): 从 markdown 中提取 YAML 内容

依赖：
    - openai: OpenAI Python SDK
    - rich: 终端美化输出
    - tools: 工具注册表（定义 AI 可调用的函数）
"""

# ============ 标准库导入 ============
import re
import json
import uuid
from typing import Optional, List, Dict

# ============ 第三方库导入 ============
import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

# ============ 本地模块导入 ============
from src.agent.prompts import get_system_prompt  # 获取 AI 系统提示词
from src.core.i18n import t  # 国际化翻译函数
from src.tools.utils.library_manager import LibraryManager  # 模板库管理
from src.core.logger import logger  # 日志记录
from src.agent.memory import MemoryManager, init_vector_memory, init_experience_library  # 内存/历史记录管理
from src.agent.graph import create_agent_app  # LangGraph Agent App

# 创建 Rich 控制台对象，用于彩色输出
console = Console()


# ============ AI 会话类 ============
class AISession:
    """
    AI 会话管理类
    
    封装与 AI 大语言模型交互所需的所有状态信息。
    负责管理对话历史、OpenAI 客户端配置、以及消息的构建和保存。
    
    属性:
        config: 包含 API 密钥、Base URL、模型名称等配置信息
        client: OpenAI 客户端实例
        model: 使用的模型名称
        history: 对话历史列表，每条消息是一个字典包含 role 和 content
    
    初始化流程:
        1. 从配置文件或磁盘加载历史记录
        2. 构建 OpenAI 客户端
        3. 加载系统提示词作为第一条消息
    """
    
    def __init__(self, config: Dict):
        """
        初始化 AI 会话
        
        参数:
            config: 配置字典，必须包含以下键：
                - api_key: API 密钥
                - base_url: API 端点地址
                - model: 模型名称
                - language: 语言设置 (en/zh)
        """
        self.config = config
        
        # 从磁盘加载历史记录（支持跨会话保存对话上下文）
        loaded_history = MemoryManager.load_history()
        
        # 创建 OpenAI 客户端
        # 支持任意兼容 OpenAI API 的服务（如 DeepSeek、Azure OpenAI 等）
        self.client = openai.OpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://api.deepseek.com")
        )
        
        # 设置使用的模型（默认为 deepseek-reasoner）
        self.model = config.get("model", "deepseek-reasoner")
        
        # 获取当前语言设置，生成对应的系统提示词
        current_lang = config.get("language", "en")
        system_prompt = get_system_prompt(current_lang)
        
        # 初始化或更新历史记录
        if not loaded_history:
            # 无历史记录，创建新的系统提示词
            self.history = [{"role": "system", "content": system_prompt}]
        else:
            # 有历史记录，更新系统提示词（保持第一条为系统消息）
            if loaded_history[0]["role"] == "system":
                loaded_history[0] = {"role": "system", "content": system_prompt}
            else:
                # 插入系统消息到最前面
                loaded_history.insert(0, {"role": "system", "content": system_prompt})
            self.history = loaded_history

    def save(self):
        """
        保存当前对话历史到磁盘
        
        每次添加新消息后自动调用，确保对话上下文持久化。
        这样用户退出后再进入，AI 仍然记得之前的对话内容。
        """
        MemoryManager.save_history(self.history)
        
    def add_user_message(self, content: str):
        """
        添加用户消息到历史记录
        
        参数:
            content: 用户输入的内容
        """
        self.history.append({"role": "user", "content": content})
        self.save()
        
    def add_assistant_message(self, content: str, tool_calls=None):
        """
        添加 AI（助手）消息到历史记录
        
        参数:
            content: AI 生成的内容
            tool_calls: 可选的函数调用列表（AI 可能同时调用多个工具）
        """
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        self.save()

    def add_tool_message(self, tool_call_id: str, content: str):
        """
       添加工具执行结果到历史记录
        
        当 AI 调用工具后，工具的执行结果需要以 "tool" 角色的消息添加到历史中。
        这样 AI 可以根据工具返回的结果决定下一步操作。
        
        参数:
            tool_call_id: 工具调用 ID，用于匹配是哪个工具调用返回的结果
            content: 工具执行结果的文本内容
        """
        self.history.append({
            "role": "tool", 
            "tool_call_id": tool_call_id,
            "content": content
        })
        self.save()

    def get_messages(self) -> List[Dict]:
        """
        获取发送给 AI 的消息列表
        
        在发送请求前调用，确保系统提示词包含最新的系统上下文信息。
        系统提示词会包含当前 Docker 容器状态、集群节点信息等实时数据。
        
        返回:
            消息列表，包含系统消息、历史对话和工具结果
        """
        # 每次获取消息时都刷新系统提示词，获取最新的系统上下文
        current_lang = self.config.get("language", "en")
        system_prompt = get_system_prompt(current_lang)
        
        # 如果第一条是系统消息，则更新它
        if self.history and self.history[0]["role"] == "system":
            self.history[0] = {"role": "system", "content": system_prompt}
        
        return self.history


# ============ 工具函数 ============

def clean_yaml_content(content: str) -> str:
    """
    从 markdown 代码块中提取 YAML 内容
    
    AI 模型返回的 YAML 通常包含在 ```yaml ``` 代码块中，
    这个函数负责提取出纯粹的 YAML 内容。
    
    参数:
        content: 包含 markdown 代码块的字符串
    
    返回:
        提取后的纯 YAML 字符串，如果找不到代码块则返回原内容
    
    示例:
        输入: "这是配置:\n```yaml\nservices:\n  redis:\n    image: redis\n```"
        输出: "services:\n  redis:\n    image: redis"
    """
    if "```yaml" in content:
        # 使用正则表达式匹配 ```yaml 到 ``` 之间的内容
        pattern = r"```yaml\n(.*?)\n```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
    return content


def convert_history_to_messages(history: List[Dict]) -> List[BaseMessage]:
    """
    Convert Pulao's dict history to LangChain BaseMessages.
    """
    messages = []
    for item in history:
        role = item.get("role")
        content = item.get("content") or ""
        
        if role == "system":
            messages.append(SystemMessage(content=content))
        elif role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = item.get("tool_calls")
            msg = AIMessage(content=content)
            if tool_calls:
                lc_tool_calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                         # Loaded from JSON or dict
                        func = tc.get("function", {})
                        func_name = func.get("name")
                        args_str = func.get("arguments", "{}")
                        try:
                            func_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except:
                            func_args = {}
                        tc_id = tc.get("id")
                    else:
                        # OpenAI Object
                        func_name = tc.function.name
                        func_args = json.loads(tc.function.arguments)
                        tc_id = tc.id
                    
                    lc_tool_calls.append({
                        "name": func_name,
                        "args": func_args,
                        "id": tc_id
                    })
                msg.tool_calls = lc_tool_calls
            messages.append(msg)
        elif role == "tool":
            tool_call_id = item.get("tool_call_id")
            messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))
    return messages


# ============ 全局会话管理 ============

# 全局 AI 会话实例（单例模式）
# CLI 应用只需要一个会话，因为是对话式交互
_CURRENT_SESSION: Optional[AISession] = None


def get_session(config: Dict) -> AISession:
    """
    获取全局 AI 会话实例
    
    使用单例模式，确保整个应用生命周期只有一个 AISession 实例。
    这样可以保持对话历史的连续性。
    
    参数:
        config: 配置字典，会传递给 AISession 构造函数
    
    返回:
        AISession 实例
    
    注意:
        如果 config 参数发生变化（如切换 AI 提供商），
        需要将 _CURRENT_SESSION 设为 None 重新创建会话。
    """
    global _CURRENT_SESSION
    if _CURRENT_SESSION is None:
        _CURRENT_SESSION = AISession(config)
    return _CURRENT_SESSION


def _perform_rag_search(instruction: str) -> str:
    """执行 RAG 向量检索，返回历史经验上下文字符串"""
    rag_context = ""
    try:
        # 优先使用新的经验库
        from src.agent.memory import init_experience_library
        exp_lib = init_experience_library()
        if exp_lib:
            results = exp_lib.search(query=instruction, top_k=3)

            if results:
                console.print(f"[dim]Found {len(results)} relevant experiences.[/dim]")
                exp_text = "\n".join([
                    f"- [{e.category}] {e.content[:200]}{'...' if len(e.content) > 200 else ''}"
                    for e in results
                ])
                rag_context = f"\n\n[Relevant Experience / 相关经验]\n{exp_text}"
                logger.info(f"RAG retrieved {len(results)} experiences")
                return rag_context
    except Exception as e:
        logger.debug(f"ExperienceLibrary not available: {e}")

    # 回退到旧的向量记忆
    try:
        vector_memory = init_vector_memory()
        if vector_memory:
            results = vector_memory.search_memory(instruction)

            # ChromaDB 返回结构: {'documents': [['mem1', 'mem2']], ...}
            if results and results.get('documents') and len(results['documents'][0]) > 0:
                memories = results['documents'][0]
                # 过滤掉空的记忆
                memories = [m for m in memories if m and m.strip()]

                if memories:
                    console.print(f"[dim]Found {len(memories)} relevant memories.[/dim]")
                    memory_text = "\n".join([f"- {m}" for m in memories])
                    rag_context = f"\n\n[Relevant History / 历史经验]\n{memory_text}"
                    logger.info(f"RAG retrieved {len(memories)} memories")
    except Exception as e:
        logger.warning(f"Failed to search vector memory: {e}")
    return rag_context


def _match_template(instruction: str) -> str:
    """匹配本地模板库，返回包含模板的扩展指令，如果没有匹配则返回空字符串"""
    template_content = None
    tpl_name = ""
    
    # 遍历所有可用模板，检查名称是否出现在用户指令中
    for name in LibraryManager.list_templates():
        if name in instruction.lower():
            tpl_name = name
            template_content = LibraryManager.get_template(tpl_name)
            if template_content:
                console.print(f"[dim]Using built-in template for: {tpl_name}[/dim]")
                break
                
    if template_content:
        return f"\n\n[Template Context]\nHere is a reference docker-compose.yml for {tpl_name}. Please adapt it:\n```yaml\n{template_content}\n```"
    return ""


def _process_new_messages(session: AISession, new_messages: list):
    """处理 LangGraph 返回的新消息并更新会话历史"""
    import json
    for msg in new_messages:
        if isinstance(msg, AIMessage):
            content = msg.content
            tool_calls = msg.tool_calls
            
            if content:
                console.print(f"\n[bold blue]AI:[/bold blue] {content}")
            
            if tool_calls:
                 # We need to convert LangChain tool calls back to OpenAI format for Pulao history
                 openai_tool_calls = []
                 for tc in tool_calls:
                     # Display
                     args_str = ", ".join([f"{k}={v}" for k, v in tc["args"].items() if k != "yaml_content"])
                     if "yaml_content" in tc["args"]:
                         args_str += ", yaml_content=<...>"
                     console.print(f"[bold cyan]Tool Call:[/bold cyan] {tc['name']}({args_str})")
                     
                     openai_tool_calls.append({
                         "id": tc["id"],
                         "type": "function",
                         "function": {
                             "name": tc["name"],
                             "arguments": json.dumps(tc["args"])
                         }
                     })
                 
                 session.add_assistant_message(content, openai_tool_calls)
            else:
                # Just content
                session.add_assistant_message(content)
                
        elif isinstance(msg, ToolMessage):
            content = msg.content
            tool_call_id = msg.tool_call_id
            
            # Display
            log_res = str(content)
            if len(log_res) > 200:
                log_res = log_res[:200] + "..."
            
            console.print(f"[bold green]Tool Result:[/bold green] {log_res}")
            session.add_tool_message(tool_call_id, content)


def _save_memory_interaction(instruction: str, new_messages: list):
    """将成功的交互保存到向量数据库中"""
    if not new_messages:
        return
        
    try:
        last_msg = new_messages[-1]
        summary = last_msg.content if isinstance(last_msg, AIMessage) else ""
        
        if not summary and isinstance(last_msg, ToolMessage):
            summary = f"Tool executed: {last_msg.tool_call_id}"
            
        if summary:
             if len(summary) > 500:
                 summary = summary[:500] + "..."
             vector_memory = init_vector_memory()
             if vector_memory:
                 vector_memory.add_memory(instruction, metadata={"result": summary})
                 logger.info("Saved interaction to memory.")
    except Exception as e:
        logger.warning(f"Failed to save memory: {e}")


# ============ 部署处理主函数 ============

def process_deployment(instruction: str, config: dict):
    """
    处理用户部署指令的核心函数
    
    这是 AI 处理流程的入口点，负责：
    1. 检查是否有匹配的模板，添加到指令上下文中
    2. 启动 ReAct Agent 循环
    3. 处理 AI 的响应（文本或工具调用）
    4. 执行工具调用并处理结果
    
    参数:
        instruction: 用户输入的自然语言指令（如 "部署一个 Redis"）
        config: 应用程序配置字典
    """
    # 获取 AI 会话实例
    session = get_session(config)

    # 1. RAG 检索
    rag_context = _perform_rag_search(instruction)
    
    # 2. 模板检查
    template_context = _match_template(instruction)
    
    # 3. 组装最终指令
    final_instruction = instruction + template_context + rag_context
    session.add_user_message(final_instruction)
    
    # 提示用户正在发送请求
    console.print(f"[dim]{t('sending_request')}[/dim]")
    logger.info(f"Sending request to AI: {instruction[:50]}...")
    
    # ============ LangGraph Execution ============
    try:
        # Initialize app
        app = create_agent_app(config)
    except Exception as e:
        logger.critical(f"Failed to initialize AI Agent: {e}", exc_info=True)
        console.print(f"[bold red]Critical Error:[/bold red] Failed to initialize AI Agent.\n{e}")
        console.print("Please check your configuration and requirements.")
        return

    try:
        # Convert history
        lc_messages = convert_history_to_messages(session.history)

        # Generate trace ID for audit logging
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

        # Run graph with security framework state
        inputs = {
            "messages": lc_messages,
            "trace_id": trace_id,
            "session_id": session_id,
            "execution_plan": None,
            "confirmed": False,
            "denied_reason": None,
            "audit_events": [],
            "confidence_result": None
        }
        result = app.invoke(inputs)
        
        # Get new messages
        all_messages = result["messages"]
        new_messages = all_messages[len(lc_messages):]
        
        # Process new messages to update history and print to console
        _process_new_messages(session, new_messages)
        
        # Memory Storage
        _save_memory_interaction(instruction, new_messages)
                
    except KeyboardInterrupt:
        console.print(f"[yellow]{t('request_cancelled')}[/yellow]")
        return
    except Exception as e:
        console.print(f"[bold red]AI Error:[/bold red] {e}")
        logger.error(f"AI Process Error: {e}", exc_info=True)
