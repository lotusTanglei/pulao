import pytest
from src.tools.registry import ToolRegistry

class TestToolRegistry:
    def setup_method(self):
        self.registry = ToolRegistry()
        
    def test_register_and_get_tool(self):
        """测试注册和获取工具"""
        @self.registry.register
        def dummy_tool(param: str) -> str:
            """Dummy docstring."""
            return f"result: {param}"
            
        tool = self.registry.get_tool("dummy_tool")
        assert tool is not None
        assert tool.__name__ == "dummy_tool"
        assert tool("test") == "result: test"
        
    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        tool = self.registry.get_tool("not_exist")
        assert tool is None
        
    def test_schema_generation(self):
        """测试 JSON Schema 生成"""
        @self.registry.register
        def compute(x: int, y: int) -> int:
            """
            计算两数之和
            
            Args:
                x: 第一个数
                y: 第二个数
            """
            return x + y
            
        schemas = self.registry.schemas
        assert len(schemas) == 1
        
        schema = schemas[0]
        assert schema["name"] == "compute"
        assert "计算两数之和" in schema["description"]
        assert "x" in schema["parameters"]["properties"]
        assert schema["parameters"]["properties"]["x"]["type"] == "integer"
