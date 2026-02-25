
import json
import inspect
from typing import Callable, Dict, List, Any, Optional
from functools import wraps

class ToolRegistry:
    """
    Registry for functions exposed to LLMs.
    Handles function registration, schema generation, and execution.
    """
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, func: Callable):
        """Decorator to register a function as a tool."""
        schema = self._generate_schema(func)
        self._tools[func.__name__] = func
        self._schemas.append(schema)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        return self._schemas

    def _generate_schema(self, func: Callable) -> Dict[str, Any]:
        """Generate OpenAI-compatible tool schema from docstring and type hints."""
        doc = func.__doc__ or ""
        description = doc.strip().split("\n")[0]
        
        sig = inspect.signature(func)
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for name, param in sig.parameters.items():
            if name == "self": 
                continue
                
            param_type = "string" # default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == dict:
                param_type = "object"
            elif param.annotation == list:
                param_type = "array"
                
            parameters["properties"][name] = {
                "type": param_type,
                "description": f"Parameter {name}" # Ideally parse from docstring
            }
            
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(name)
                
        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": parameters
            }
        }

# Global registry instance
registry = ToolRegistry()

# --- Tool Definitions ---

from src.docker_ops import deploy_compose, deploy_cluster
from src.system_ops import execute_shell_command
from src.logger import logger

@registry.register
def deploy_service(yaml_content: str, project_name: str) -> str:
    """
    Deploy a single-node service using Docker Compose.
    
    Args:
        yaml_content: The full content of docker-compose.yml
        project_name: Name of the project (folder name)
    """
    try:
        result = deploy_compose(yaml_content, project_name)
        if result.success:
            return f"Success: {result.message}\n{result.stdout}"
        else:
            return f"Error: {result.message}\n{result.stderr}"
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def deploy_cluster_service(plan_content: dict, project_name: str) -> str:
    """
    Deploy a multi-node service cluster.
    
    Args:
        plan_content: Dictionary mapping node names to docker-compose.yml content
        project_name: Name of the project
    """
    try:
        success, fail, errors = deploy_cluster(plan_content, project_name)
        if fail == 0:
            return f"Cluster deployment success! ({success} nodes)"
        else:
            return f"Cluster deployment partial failure. Success: {success}, Fail: {fail}. Errors: {'; '.join(errors)}"
    except Exception as e:
        return f"Exception: {str(e)}"

@registry.register
def execute_command(command: str) -> str:
    """
    Execute a shell command on the local system.
    Use this for checking system status, reading files, etc.
    """
    try:
        logger.info(f"Executing shell command: {command}")
        # Re-using execute_shell_command but capturing output?
        # The original function prints to console. We need one that returns string.
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return f"Stdout: {result.stdout}"
        else:
            return f"Stderr: {result.stderr}"
    except Exception as e:
        return f"Exception: {str(e)}"

