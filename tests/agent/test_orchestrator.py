import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent.orchestrator import _match_template, _process_new_messages

class TestOrchestrator:
    @patch("src.agent.orchestrator.LibraryManager")
    def test_match_template_found(self, mock_library):
        mock_library.list_templates.return_value = ["redis", "nginx"]
        mock_library.get_template.return_value = "version: '3'\nservices:\n  redis:\n    image: redis"
        result = _match_template("帮我部署一个 redis 服务")
        assert "[Template Context]" in result
        assert "image: redis" in result
        
    @patch("src.agent.orchestrator.LibraryManager")
    def test_match_template_not_found(self, mock_library):
        mock_library.list_templates.return_value = ["redis", "nginx"]
        result = _match_template("帮我部署一个 mysql 服务")
        assert result == ""

    def test_process_new_messages(self):
        session = MagicMock()
        msg1 = AIMessage(content="好的，我来帮你处理。")
        msg2 = AIMessage(content="", tool_calls=[{"name": "check_port_available", "args": {"port": 8080}, "id": "call_1"}])
        msg3 = ToolMessage(content="Port 8080 is available", tool_call_id="call_1")
        _process_new_messages(session, [msg1, msg2, msg3])
        assert session.add_assistant_message.call_count == 2
        session.add_tool_message.assert_called_once_with("call_1", "Port 8080 is available")
