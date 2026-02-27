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
from typing import Optional, List, Dict

# ============ 第三方库导入 ============
import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt

# ============ 本地模块导入 ============
from src.system_ops import execute_shell_command  # 执行 Shell 命令工具
from src.prompts import get_system_prompt  # 获取 AI 系统提示词
from src.i18n import t  # 国际化翻译函数
from src.library_manager import LibraryManager  # 模板库管理
from src.logger import logger  # 日志记录
from src.memory import MemoryManager, init_vector_memory  # 内存/历史记录管理
from src.tools import registry  # 工具注册表

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


def extract_json(content: str) -> Optional[Dict]:
    """
    从 AI 响应中提取 JSON 数据
    
    AI 可能以多种格式返回 JSON：
    1. 直接返回 JSON 字符串
    2. 包裹在 ```json ``` 代码块中
    3. 嵌入在文本中（找到第一个 { 和最后一个 }）
    
    这个函数尝试所有这些方式提取 JSON。
    
    参数:
        content: AI 生成的文本内容
    
    返回:
        解析后的字典对象，提取失败返回 None
    
    注意:
        这个函数是备用方案，现代版本优先使用工具调用（Function Calling）
        与 AI 交互，因为工具调用能更可靠地获取结构化数据。
    """
    # 方法1：直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        
    # 方法2：从 ```json ``` 代码块中提取
    match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 方法3：从文本中找第一个 { 到最后一个 }
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1:
        json_str = content[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
    return None


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
    
    ReAct 循环流程:
        1. 发送用户指令和历史消息给 AI
        2. AI 可能返回：
           - 文本回答（直接显示给用户）
           - 工具调用请求（需要执行工具）
        3. 如果是工具调用：
           - 显示工具名称和参数
           - 对于危险操作（部署、执行命令）需要用户确认
           - 执行工具并获取结果
           - 将结果添加到历史，询问 AI 下一步
        4. 重复直到 AI 返回最终答案或达到最大轮次（10 轮）
    
    异常:
        KeyboardInterrupt: 用户取消请求
        其他 Exception: AI 处理或工具执行错误
    """
    # 获取 AI 会话实例
    session = get_session(config)

    # ============ RAG 检索 ============
    rag_context = ""
    try:
        vector_memory = init_vector_memory()
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
    
    # ============ 模板检查 ============
    # 检查用户的指令是否匹配模板库中的某个模板
    # 例如用户说 "部署 Redis"，模板库中有 redis 模板
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
    
    # 如果找到匹配的模板，将模板内容添加到指令中作为参考
    final_instruction = instruction
    if template_content:
        final_instruction += f"\n\n[Template Context]\nHere is a reference docker-compose.yml for {tpl_name}. Please adapt it:\n```yaml\n{template_content}\n```"
    
    # 添加 RAG 检索结果
    if rag_context:
        final_instruction += rag_context
    
    # 添加用户消息到历史记录
    session.add_user_message(final_instruction)
    
    # 提示用户正在发送请求
    console.print(f"[dim]{t('sending_request')}[/dim]")
    logger.info(f"Sending request to AI: {instruction[:50]}...")
    
    # ============ ReAct Agent 循环 ============
    # 最大循环轮次，防止 AI 进入无限循环
    MAX_TURNS = 10
    turn_count = 0
    
    while turn_count < MAX_TURNS:
        turn_count += 1
        try:
            # 调用 AI 模型
            # 参数说明：
            # - model: 使用的模型
            # - messages: 对话历史（包含系统提示、用户消息、之前的结果）
            # - temperature: 创造性参数，较低的值会让输出更确定性
            # - tools: 工具注册表，定义 AI 可以调用的函数
            # - tool_choice: 自动选择调用哪个工具
            response = session.client.chat.completions.create(
                model=session.model,
                messages=session.get_messages(),
                temperature=0.2,
                tools=registry.schemas,
                tool_choice="auto"
            )
            
            # 获取 AI 的响应消息
            message = response.choices[0].message
            content = message.content  # AI 的文本回答
            tool_calls = message.tool_calls  # AI 调用的工具列表
            
            # 如果 AI 返回了文本内容，显示给用户
            # 对于 deepseek-reasoner 等模型，这里可能包含推理过程
            if content:
                console.print(f"\n[bold blue]AI:[/bold blue] {content}")
                session.add_assistant_message(content, tool_calls)
            elif tool_calls:
                # 如果只有工具调用没有文本，也需要添加到历史
                session.add_assistant_message("", tool_calls)

            # ============ 无工具调用 ============
            # 如果 AI 没有请求调用工具，说明是最终答案或需要澄清问题
            if not tool_calls:
                # 备用方案：检查是否返回了旧格式的 JSON
                if content:
                    legacy_json = extract_json(content)
                    if legacy_json and isinstance(legacy_json, dict):
                        msg_type = legacy_json.get("type")
                        # 如果是提问类型，显示问题
                        if msg_type == "question":
                            console.print(f"\n[bold yellow]AI Question:[/bold yellow] {legacy_json.get('content')}")
                            # 视为最终响应，用户需要回答
                            break
                        # 其他类型（plan/command）的处理...
                # 没有更多操作，退出循环
                break
            
            # ============ 处理工具调用 ============
            # AI 请求调用一个或多个工具
            for tool_call in tool_calls:
                # 解析工具调用信息
                func_name = tool_call.function.name  # 工具名称
                func_args = json.loads(tool_call.function.arguments)  # 工具参数
                tool_call_id = tool_call.id  # 工具调用 ID，用于返回结果
                
                # 友好地显示工具调用（隐藏过长的 YAML 内容）
                args_str = ", ".join([f"{k}={v}" for k, v in func_args.items() if k != "yaml_content"])
                if "yaml_content" in func_args:
                    args_str += ", yaml_content=<...>"
                
                console.print(f"[bold cyan]Tool Call:[/bold cyan] {func_name}({args_str})")
                logger.info(f"Executing tool: {func_name} with args: {args_str}")
                
                # 从注册表中获取工具函数
                func = registry.get_tool(func_name)
                if not func:
                    error_msg = f"Error: Tool {func_name} not found."
                    session.add_tool_message(tool_call_id, error_msg)
                    continue
                
                # 执行工具
                try:
                    # 对于危险操作，需要用户确认
                    # 这些操作可能会部署服务或执行命令，有潜在风险
                    if func_name in ["deploy_service", "deploy_cluster_service", "execute_command"]:
                        if not Confirm.ask(f"Allow AI to run {func_name}?"):
                            session.add_tool_message(tool_call_id, "User denied permission.")
                            console.print("[yellow]Action denied by user.[/yellow]")
                            continue

                    # 执行工具函数，获取返回结果
                    result = func(**func_args)
                    
                    # 显示工具执行结果
                    console.print(f"[bold green]Tool Result:[/bold green] {result}")
                    
                    # 将结果添加工具消息到历史，供 AI 下一轮决策使用
                    session.add_tool_message(tool_call_id, str(result))
                    
                    # 截断日志输出，避免过长
                    log_res = str(result)
                    if len(log_res) > 200: 
                        log_res = log_res[:200] + "..."
                    logger.info(f"Tool result: {log_res}")
                    
                except Exception as e:
                    # 工具执行出错，记录错误并通知 AI
                    error_msg = f"Tool execution error: {str(e)}"
                    console.print(f"[bold red]Tool Error:[/bold red] {error_msg}")
                    logger.error(error_msg)
                    session.add_tool_message(tool_call_id, error_msg)
                    # 循环继续，AI 会看到错误并尝试修复或换一种方式
                    
        except KeyboardInterrupt:
            # 用户取消请求
            console.print(f"[yellow]{t('request_cancelled')}[/yellow]")
            return

        except Exception as e:
            # 其他错误
            console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
            logger.error(f"AI Process Error: {e}", exc_info=True)
            raise

    # ============ 记忆存储 ============
    if turn_count > 0:
        try:
            # 获取最后一条消息作为总结
            last_msg = session.history[-1]
            summary = last_msg.get("content", "")
            
            # 如果是工具调用结果，可能没有 content 或者 content 很长
            if not summary and last_msg.get("role") == "tool":
                summary = f"Tool executed: {last_msg.get('tool_call_id')}"
            
            if summary:
                # 截断过长的总结
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                
                vector_memory = init_vector_memory()
                vector_memory.add_memory(instruction, metadata={"result": summary})
                logger.info("Saved interaction to memory.")
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")
