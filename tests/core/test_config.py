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
        
    @patch("src.core.config.os.environ.get")
    def test_get_provider_config_from_env(self, mock_env_get):
        """测试优先从环境变量读取配置"""
        mock_env_get.side_effect = lambda k, d=None: "env-api-key" if "API_KEY" in k else d
        
        provider_cfg = get_provider_config({
            "current_provider": "openai",
            "providers": {"openai": {"api_key": "file-key", "base_url": "file-url"}}
        })
        
        # base_url 在环境变量中没有，应该使用配置文件的
        # assert provider_cfg["base_url"] == "file-url"
