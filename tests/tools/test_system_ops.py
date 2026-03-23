import pytest
from unittest.mock import patch, MagicMock
from src.tools.system.system_ops import execute_shell_command, check_port_available

class TestSystemOps:
    @patch("src.tools.system.system_ops.run_command")
    def test_execute_shell_command_success(self, mock_run):
        """测试执行 shell 命令"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello world\n"
        mock_run.return_value = mock_result
        
        result = execute_shell_command("echo 'hello world'")
        
        # 验证传入 run_command 的是列表而不是字符串
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["sh", "-c", "echo 'hello world'"]
        assert "hello world" in result
        
    @patch("src.tools.system.system_ops.socket.socket")
    def test_check_port_available(self, mock_socket):
        """测试端口可用性检查"""
        mock_socket_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        # 正常绑定代表可用
        result = check_port_available(8080)
        assert "is available" in result
        mock_socket_instance.bind.assert_called_with(('0.0.0.0', 8080))
        
        # 抛出 OSError 代表被占用
        mock_socket_instance.bind.side_effect = OSError()
        result = check_port_available(8081)
        assert "is currently occupied" in result
