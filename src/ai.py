
import openai
from rich.console import Console
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
import re
import json
from typing import Optional, List, Dict
from src.system_ops import execute_shell_command
from src.prompts import get_system_prompt
from src.i18n import t
from src.library_manager import LibraryManager
from src.logger import logger
from src.memory import MemoryManager
from src.tools import registry

console = Console()

class AISession:
    """Encapsulates AI interaction state and configuration."""
    def __init__(self, config: Dict):
        self.config = config
        
        # Load history from file, or initialize new
        loaded_history = MemoryManager.load_history()
        
        # Always ensure system prompt is the first message
        base_url = config.get("base_url", "https://api.deepseek.com")
        if base_url.endswith("/chat/completions"):
            base_url = base_url.replace("/chat/completions", "")
        
        self.client = openai.OpenAI(
            api_key=config.get("api_key", ""),
            base_url=base_url
        )
        self.model = config.get("model", "deepseek-reasoner")
        
        current_lang = config.get("language", "en")
        system_prompt = get_system_prompt(current_lang)
        
        if not loaded_history:
            self.history = [{"role": "system", "content": system_prompt}]
        else:
            # If loaded, update the system prompt (first msg)
            if loaded_history[0]["role"] == "system":
                loaded_history[0] = {"role": "system", "content": system_prompt}
            else:
                loaded_history.insert(0, {"role": "system", "content": system_prompt})
            self.history = loaded_history

    def save(self):
        """Save current history to disk."""
        MemoryManager.save_history(self.history)
        
    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})
        self.save()
        
    def add_assistant_message(self, content: str, tool_calls=None):
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)
        self.save()

    def add_tool_message(self, tool_call_id: str, content: str):
        self.history.append({
            "role": "tool", 
            "tool_call_id": tool_call_id,
            "content": content
        })
        self.save()

    def get_messages(self) -> List[Dict]:
        # Always refresh system prompt with latest system info before sending
        current_lang = self.config.get("language", "en")
        system_prompt = get_system_prompt(current_lang)
        if self.history and self.history[0]["role"] == "system":
            self.history[0] = {"role": "system", "content": system_prompt}
        return self.history

def clean_yaml_content(content: str) -> str:
    """Extract YAML from markdown block if present."""
    if "```yaml" in content:
        pattern = r"```yaml\n(.*?)\n```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
    return content

def extract_json(content: str) -> Optional[Dict]:
    """Fallback: Extract JSON from AI response if tool calls failed."""
    try:
        # First try direct parse
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        
    # Try finding JSON block
    match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { and last }
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1:
        json_str = content[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
            
    return None

# Global session cache (simple approach for CLI REPL)
_CURRENT_SESSION: Optional[AISession] = None

def get_session(config: Dict) -> AISession:
    global _CURRENT_SESSION
    if _CURRENT_SESSION is None:
        _CURRENT_SESSION = AISession(config)
    return _CURRENT_SESSION

def process_deployment(instruction: str, config: dict):
    session = get_session(config)
    
    # Check for available templates based on user instruction
    template_content = None
    tpl_name = ""
    for name in LibraryManager.list_templates():
        if name in instruction.lower():
            tpl_name = name
            template_content = LibraryManager.get_template(tpl_name)
            if template_content:
                console.print(f"[dim]Using built-in template for: {tpl_name}[/dim]")
                break
    
    final_instruction = instruction
    if template_content:
        final_instruction += f"\n\n[Template Context]\nHere is a reference docker-compose.yml for {tpl_name}. Please adapt it:\n```yaml\n{template_content}\n```"
    
    session.add_user_message(final_instruction)
    
    console.print(f"[dim]{t('sending_request')}[/dim]")
    logger.info(f"Sending request to AI: {instruction[:50]}...")
    
    # ReAct Loop (Max 10 turns to prevent infinite loops)
    MAX_TURNS = 10
    turn_count = 0
    
    while turn_count < MAX_TURNS:
        turn_count += 1
        try:
            response = session.client.chat.completions.create(
                model=session.model,
                messages=session.get_messages(),
                temperature=0.2,
                tools=registry.schemas,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            content = message.content
            tool_calls = message.tool_calls
            
            # Display reasoning content if available (for deepseek-reasoner or similar)
            # Standard OpenAI API puts content in message.content
            if content:
                console.print(f"\n[bold blue]AI:[/bold blue] {content}")
                session.add_assistant_message(content, tool_calls)
            elif tool_calls:
                # If only tool calls, we still need to add message to history
                session.add_assistant_message("", tool_calls)

            # If no tool calls, this is the final answer or a clarification question
            if not tool_calls:
                # Fallback: Check if AI output legacy JSON format despite instructions
                if content:
                    legacy_json = extract_json(content)
                    if legacy_json and isinstance(legacy_json, dict):
                        msg_type = legacy_json.get("type")
                        # If it's a question, print it nicely
                        if msg_type == "question":
                            console.print(f"\n[bold yellow]AI Question:[/bold yellow] {legacy_json.get('content')}")
                            # We treat this as a final response for this turn, user needs to answer
                            break
                        # If it's a plan or command (legacy), warn user but try to handle?
                        # Actually, for Agent mode, we prefer tools. But if model fails, maybe we can map legacy JSON to tool call?
                        # For now, just break and show content.
                break
            
            # Handle Tool Calls
            for tool_call in tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id
                
                console.print(f"[dim]Tool Call: {func_name}[/dim]")
                logger.info(f"Executing tool: {func_name}")
                
                # Get the function from registry
                func = registry.get_tool(func_name)
                if not func:
                    error_msg = f"Error: Tool {func_name} not found."
                    session.add_tool_message(tool_call_id, error_msg)
                    continue
                
                # Execute
                try:
                    # For dangerous tools, we might want confirmation
                    if func_name in ["deploy_service", "deploy_cluster_service", "execute_command"]:
                        if not Confirm.ask(f"Allow AI to run {func_name}?"):
                            session.add_tool_message(tool_call_id, "User denied permission.")
                            console.print("[yellow]Action denied by user.[/yellow]")
                            continue

                    result = func(**func_args)
                    session.add_tool_message(tool_call_id, str(result))
                    
                    # If result is large, truncate for log
                    log_res = str(result)
                    if len(log_res) > 200: 
                        log_res = log_res[:200] + "..."
                    logger.info(f"Tool result: {log_res}")
                    
                except Exception as e:
                    error_msg = f"Tool execution error: {str(e)}"
                    logger.error(error_msg)
                    session.add_tool_message(tool_call_id, error_msg)
                    # The loop continues, AI sees the error and can retry/fix
                    
        except KeyboardInterrupt:
            console.print(f"[yellow]{t('request_cancelled')}[/yellow]")
            return

        except Exception as e:
            console.print(f"[bold red]{t('ai_error')}[/bold red] {e}")
            logger.error(f"AI Process Error: {e}", exc_info=True)
            raise
