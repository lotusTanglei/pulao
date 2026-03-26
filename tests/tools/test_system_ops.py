import pytest
from unittest.mock import patch, MagicMock
from src.tools.system.system_ops import execute_shell_command, check_port_available

class TestSystemOps:
    @patch("src.tools.system.system_ops.subprocess.Popen")
    def test_execute_shell_command_success(self, mock_popen):
        """测试执行 shell 命令"""
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["hello world\n", ""]
        mock_process.poll.side_effect = [None, 0]
        mock_process.stderr.read.return_value = ""
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        execute_shell_command("echo 'hello world'")
        
        mock_popen.assert_called_once_with(
            "echo 'hello world'", 
            shell=True,
            stdout=-1, # subprocess.PIPE is -1
            stderr=-1,
            text=True,
            executable="/bin/bash"
        )
        
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
