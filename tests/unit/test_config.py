"""配置加载器测试."""

import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml
from pydantic import ValidationError

from flowpilot.config.loader import ConfigLoader, load_config
from flowpilot.config.schema import FlowPilotConfig


@pytest.fixture
def valid_config():
    """有效的配置示例."""
    return {
        "llm": {
            "default_provider": "claude",
            "providers": {
                "claude": {
                    "model": "claude-sonnet-4.5",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }
            },
        },
        "hosts": {
            "test-host": {
                "env": "dev",
                "user": "ubuntu",
                "addr": "192.168.1.100",
                "port": 22,
            }
        },
        "jumps": {},
        "services": {},
        "policies": [],
    }


@pytest.fixture
def temp_config_file(tmp_path, valid_config):
    """创建临时配置文件."""
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(valid_config, f)
    return config_file


def test_load_valid_config(temp_config_file):
    """测试加载有效配置."""
    loader = ConfigLoader(temp_config_file)
    config = loader.load()

    assert isinstance(config, FlowPilotConfig)
    assert config.llm.default_provider == "claude"
    assert "test-host" in config.hosts


def test_load_nonexistent_file():
    """测试加载不存在的文件."""
    loader = ConfigLoader("/nonexistent/path/config.yaml")

    with pytest.raises(FileNotFoundError) as exc_info:
        loader.load()

    assert "配置文件不存在" in str(exc_info.value)
    assert "flowpilot init" in str(exc_info.value)


def test_load_invalid_yaml(tmp_path):
    """测试加载无效的 YAML."""
    invalid_file = tmp_path / "invalid.yaml"
    with open(invalid_file, "w") as f:
        f.write("invalid: yaml: content: [")

    loader = ConfigLoader(invalid_file)

    with pytest.raises(ValueError) as exc_info:
        loader.load()

    assert "YAML 解析失败" in str(exc_info.value)


def test_load_missing_required_fields(tmp_path):
    """测试缺少必填字段."""
    incomplete_file = tmp_path / "incomplete.yaml"
    with open(incomplete_file, "w") as f:
        yaml.dump({"hosts": {}}, f)  # 缺少 llm 字段

    loader = ConfigLoader(incomplete_file)

    with pytest.raises(ValueError) as exc_info:
        loader.load()

    assert "配置校验失败" in str(exc_info.value)
    assert "llm" in str(exc_info.value)


def test_validate_success(temp_config_file):
    """测试配置校验成功."""
    loader = ConfigLoader(temp_config_file)
    is_valid, message = loader.validate()

    assert is_valid is True
    assert "配置文件有效" in message


def test_validate_failure():
    """测试配置校验失败."""
    loader = ConfigLoader("/nonexistent/path/config.yaml")
    is_valid, message = loader.validate()

    assert is_valid is False
    assert "配置文件不存在" in message


def test_get_api_key():
    """测试获取 API Key."""
    with patch.dict(os.environ, {"TEST_API_KEY": "sk-test-12345"}):
        api_key = ConfigLoader.get_api_key("TEST_API_KEY")
        assert api_key == "sk-test-12345"

    # 测试不存在的环境变量
    api_key = ConfigLoader.get_api_key("NONEXISTENT_KEY")
    assert api_key is None


def test_load_env(tmp_path):
    """测试 .env 文件加载."""
    # 创建 .env 文件
    env_file = tmp_path / ".env"
    with open(env_file, "w") as f:
        f.write("TEST_KEY=test_value\n")

    # 模拟 DEFAULT_CONFIG_DIR 为 tmp_path
    with patch.object(ConfigLoader, "DEFAULT_CONFIG_DIR", tmp_path):
        loader = ConfigLoader()

        # 验证环境变量已加载
        assert os.getenv("TEST_KEY") == "test_value"


def test_load_config_shortcut(temp_config_file):
    """测试 load_config 快捷函数."""
    config = load_config(temp_config_file)

    assert isinstance(config, FlowPilotConfig)
    assert config.llm.default_provider == "claude"
