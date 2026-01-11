"""Policy Engine 和命令分类器测试."""

import pytest

from flowpilot.config.schema import FlowPilotConfig, LLMConfig, LLMProviderConfig, PolicyCondition, PolicyRule
from flowpilot.policy.action_classifier import ActionType, classify_command, get_risk_level, is_destructive
from flowpilot.policy.engine import PolicyDecision, PolicyEffect, PolicyEngine


# ========== 命令分类器测试 ==========


def test_classify_read_command():
    """测试只读命令分类."""
    assert classify_command("ls -la") == ActionType.READ
    assert classify_command("cat /etc/hosts") == ActionType.READ
    assert classify_command("grep error /var/log/app.log") == ActionType.READ
    assert classify_command("ps aux") == ActionType.READ


def test_classify_write_command():
    """测试写操作命令分类."""
    assert classify_command("rm /tmp/test.txt") == ActionType.WRITE
    assert classify_command("mv file1.txt file2.txt") == ActionType.WRITE
    assert classify_command("systemctl stop nginx") == ActionType.WRITE
    assert classify_command("kill -9 1234") == ActionType.WRITE
    assert classify_command("echo 'test' > /tmp/file") == ActionType.WRITE


def test_classify_destructive_command():
    """测试破坏性命令分类."""
    assert classify_command("rm -rf /") == ActionType.DESTRUCTIVE
    assert classify_command("mkfs.ext4 /dev/sda1") == ActionType.DESTRUCTIVE
    assert classify_command("dd if=/dev/zero of=/dev/sda") == ActionType.DESTRUCTIVE
    assert classify_command("shutdown now") == ActionType.DESTRUCTIVE
    assert classify_command("reboot") == ActionType.DESTRUCTIVE


def test_is_destructive():
    """测试破坏性判断函数."""
    assert is_destructive("rm -rf /") is True
    assert is_destructive("ls -la") is False
    assert is_destructive("rm file.txt") is False


def test_get_risk_level():
    """测试风险级别评估."""
    # 读操作
    assert get_risk_level("ls -la", "dev") == "low"
    assert get_risk_level("ls -la", "prod") == "low"

    # 写操作
    assert get_risk_level("rm file.txt", "dev") == "medium"
    assert get_risk_level("rm file.txt", "prod") == "high"

    # 破坏性操作
    assert get_risk_level("rm -rf /", "dev") == "high"
    assert get_risk_level("rm -rf /", "prod") == "critical"


# ========== Policy Engine 测试 ==========


@pytest.fixture
def mock_config():
    """创建测试配置."""
    return FlowPilotConfig(
        llm=LLMConfig(
            default_provider="claude",
            providers={
                "claude": LLMProviderConfig(
                    model="claude-sonnet-4",
                    api_key_env="ANTHROPIC_API_KEY",
                )
            },
        ),
        policies=[
            PolicyRule(
                name="prod_write_protection",
                condition=PolicyCondition(env="prod", action_type="write"),
                effect="require_confirm",
                message="生产环境写操作需要确认",
            ),
            PolicyRule(
                name="destructive_deny",
                condition=PolicyCondition(env="prod", action_type="destructive"),
                effect="deny",
                message="禁止在生产环境执行破坏性操作",
            ),
            PolicyRule(
                name="batch_operation_limit",
                condition=PolicyCondition(target_count=">5"),
                effect="require_confirm",
                message="批量操作超过 5 台主机需要确认",
            ),
        ],
    )


def test_policy_engine_allow(mock_config):
    """测试允许执行的策略."""
    engine = PolicyEngine(mock_config)

    # dev 环境的读操作应该被允许
    decision = engine.check(
        tool_name="ssh_exec",
        args={"command": "ls -la", "host": "dev-server"},
        env="dev",
        action_type=ActionType.READ,
    )

    assert decision.effect == PolicyEffect.ALLOW
    assert decision.triggered_rule is None


def test_policy_engine_require_confirm(mock_config):
    """测试需要确认的策略."""
    engine = PolicyEngine(mock_config)

    # prod 环境的写操作需要确认
    decision = engine.check(
        tool_name="ssh_exec",
        args={"command": "rm /tmp/file", "host": "prod-server"},
        env="prod",
        action_type=ActionType.WRITE,
    )

    assert decision.effect == PolicyEffect.REQUIRE_CONFIRM
    assert decision.triggered_rule == "prod_write_protection"
    assert decision.confirm_token is not None
    assert "生产环境写操作" in decision.message


def test_policy_engine_deny(mock_config):
    """测试拒绝执行的策略."""
    engine = PolicyEngine(mock_config)

    # prod 环境的破坏性操作应该被拒绝
    decision = engine.check(
        tool_name="ssh_exec",
        args={"command": "rm -rf /", "host": "prod-server"},
        env="prod",
        action_type=ActionType.DESTRUCTIVE,
    )

    assert decision.effect == PolicyEffect.DENY
    assert decision.triggered_rule == "destructive_deny"
    assert decision.confirm_token is None
    assert "禁止" in decision.message


def test_policy_engine_batch_limit(mock_config):
    """测试批量操作限制."""
    engine = PolicyEngine(mock_config)

    # 超过 5 台主机的批量操作需要确认
    decision = engine.check(
        tool_name="ssh_exec_batch",
        args={"hosts": ["host1", "host2", "host3", "host4", "host5", "host6"], "command": "uptime"},
    )

    assert decision.effect == PolicyEffect.REQUIRE_CONFIRM
    assert decision.triggered_rule == "batch_operation_limit"


def test_policy_engine_confirm_token():
    """测试确认 token 验证."""
    config = FlowPilotConfig(
        llm=LLMConfig(
            default_provider="claude",
            providers={
                "claude": LLMProviderConfig(
                    model="claude-sonnet-4",
                    api_key_env="ANTHROPIC_API_KEY",
                )
            },
        ),
        policies=[
            PolicyRule(
                name="test_confirm",
                condition=PolicyCondition(env="prod"),
                effect="require_confirm",
                message="测试确认",
            )
        ],
    )

    engine = PolicyEngine(config)

    # 生成 token
    decision = engine.check(
        tool_name="ssh_exec",
        args={"command": "test", "host": "test"},
        env="prod",
    )

    token = decision.confirm_token
    assert token is not None

    # 验证 token
    assert engine.validate_confirm_token(token) is True
    assert engine.validate_confirm_token("invalid_token") is False

    # 消费 token
    consumed = engine.consume_confirm_token(token)
    assert consumed is not None

    # token 应该已被消费（一次性）
    assert engine.validate_confirm_token(token) is False


def test_policy_engine_no_env_matching(mock_config):
    """测试环境不匹配的情况."""
    engine = PolicyEngine(mock_config)

    # staging 环境的写操作不会触发 prod_write_protection
    decision = engine.check(
        tool_name="ssh_exec",
        args={"command": "rm file", "host": "staging-server"},
        env="staging",
        action_type=ActionType.WRITE,
    )

    assert decision.effect == PolicyEffect.ALLOW


def test_policy_target_count_conditions(mock_config):
    """测试目标数量条件."""
    engine = PolicyEngine(mock_config)

    # 5 台主机不会触发（>5）
    decision1 = engine.check(
        tool_name="ssh_exec_batch",
        args={"hosts": ["h1", "h2", "h3", "h4", "h5"], "command": "test"},
    )
    assert decision1.effect == PolicyEffect.ALLOW

    # 6 台主机会触发（>5）
    decision2 = engine.check(
        tool_name="ssh_exec_batch",
        args={"hosts": ["h1", "h2", "h3", "h4", "h5", "h6"], "command": "test"},
    )
    assert decision2.effect == PolicyEffect.REQUIRE_CONFIRM
