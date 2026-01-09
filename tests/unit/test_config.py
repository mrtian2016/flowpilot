"""配置模块测试."""

import pytest
from pydantic import ValidationError

from flowpilot.config.schema import (
    FlowPilotConfig,
    HostConfig,
    LLMConfig,
    LLMProviderConfig,
)


def test_llm_provider_config_valid():
    """测试 LLM Provider 配置验证."""
    config = LLMProviderConfig(
        model="claude-sonnet-4.5",
        api_key_env="ANTHROPIC_API_KEY",
        max_tokens=4096,
        temperature=0.7,
    )
    assert config.model == "claude-sonnet-4.5"
    assert config.max_tokens == 4096


def test_llm_provider_config_invalid_temperature():
    """测试温度参数验证."""
    with pytest.raises(ValidationError):
        LLMProviderConfig(
            model="claude-sonnet-4.5",
            api_key_env="ANTHROPIC_API_KEY",
            temperature=3.0,  # 超出范围
        )


def test_host_config_valid():
    """测试主机配置验证."""
    config = HostConfig(
        env="prod",
        user="ubuntu",
        addr="10.0.1.1",
        port=22,
        tags=["api", "payment"],
    )
    assert config.env == "prod"
    assert len(config.tags) == 2


def test_host_config_defaults():
    """测试主机配置默认值."""
    config = HostConfig(
        env="staging",
        user="ubuntu",
        addr="staging-api-1",
    )
    assert config.port == 22  # 默认端口
    assert config.tags == []  # 默认空列表


def test_llm_config_valid():
    """测试 LLM 配置."""
    config = LLMConfig(
        default_provider="claude",
        providers={
            "claude": LLMProviderConfig(
                model="claude-sonnet-4.5",
                api_key_env="ANTHROPIC_API_KEY",
            ),
        },
    )
    assert config.default_provider == "claude"
    assert "claude" in config.providers


def test_flowpilot_config_minimal():
    """测试最小 FlowPilot 配置."""
    config = FlowPilotConfig(
        llm=LLMConfig(
            default_provider="claude",
            providers={
                "claude": LLMProviderConfig(
                    model="claude-sonnet-4.5",
                    api_key_env="ANTHROPIC_API_KEY",
                ),
            },
        ),
    )
    assert config.llm.default_provider == "claude"
    assert len(config.hosts) == 0  # 默认空字典
    assert len(config.policies) == 0  # 默认空列表
