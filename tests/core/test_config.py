import pytest
import os
from unittest.mock import patch, mock_open
from src.core.config import load_config

class TestConfig:
    @patch("src.core.config.os.path.exists")
    @patch("src.core.config.open", new_callable=mock_open, read_data="current_provider: openai\nproviders:\n  openai:\n    api_key: test-key")
    def test_load_config_success(self, mock_file, mock_exists):
        """测试加载配置文件"""
        mock_exists.return_value = True
        config = load_config()
        
        assert config["current_provider"] == "openai"
        assert "openai" in config["providers"]
        assert config["providers"]["openai"]["api_key"] == "test-key"
