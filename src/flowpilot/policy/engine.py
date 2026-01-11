"""策略引擎 - 执行前安全检查."""

import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..config.schema import FlowPilotConfig, PolicyCondition, PolicyRule
from .action_classifier import ActionType, classify_command


class PolicyEffect(str, Enum):
    """策略效果."""

    ALLOW = "allow"  # 允许执行
    REQUIRE_CONFIRM = "require_confirm"  # 需要用户确认
    DENY = "deny"  # 拒绝执行


@dataclass
class PolicyDecision:
    """策略决策结果."""

    effect: PolicyEffect  # 决策效果
    message: str  # 提示消息
    triggered_rule: str | None = None  # 触发的规则名称
    confirm_token: str | None = None  # 确认 token（require_confirm 时生成）
    risk_level: str = "low"  # 风险级别
    metadata: dict[str, Any] | None = None  # 额外元数据


class PolicyEngine:
    """策略引擎."""

    # Token 过期时间（秒）
    TOKEN_TTL_SECONDS = 300  # 5 分钟

    def __init__(self, config: FlowPilotConfig) -> None:
        """初始化策略引擎.

        Args:
            config: FlowPilot 配置
        """
        self.config = config
        self._confirm_tokens: dict[str, dict[str, Any]] = {}  # token -> 请求信息


    def check(
        self,
        tool_name: str,
        args: dict[str, Any],
        env: str | None = None,
        action_type: ActionType | None = None,
    ) -> PolicyDecision:
        """检查操作是否符合策略.

        Args:
            tool_name: Tool 名称
            args: Tool 参数
            env: 环境（dev/staging/prod）
            action_type: 操作类型（如果为 None，会自动推断）

        Returns:
            策略决策
        """
        # 自动推断环境（从 args 或配置）
        if not env:
            env = args.get("env", "dev")

        # 自动推断操作类型（SSH 命令）
        if not action_type and tool_name == "ssh_exec":
            command = args.get("command", "")
            action_type = classify_command(command)

        # 获取目标数量（批量操作）
        target_count = self._get_target_count(tool_name, args)

        # 匹配规则
        for rule in self.config.policies:
            if self._match_rule(rule, env, action_type, target_count):
                return self._create_decision(rule, env, action_type, args)

        # 默认允许
        return PolicyDecision(
            effect=PolicyEffect.ALLOW,
            message="操作已允许",
            risk_level="low",
        )

    def validate_confirm_token(self, token: str) -> bool:
        """验证确认 token（含过期检查）.

        Args:
            token: 确认 token

        Returns:
            是否有效
        """
        import time

        if token not in self._confirm_tokens:
            return False

        token_data = self._confirm_tokens[token]
        created_at = token_data.get("created_at", 0)

        # 检查是否过期
        if time.time() - created_at > self.TOKEN_TTL_SECONDS:
            # 清理过期 token
            del self._confirm_tokens[token]
            return False

        return True

    def consume_confirm_token(self, token: str) -> dict[str, Any] | None:
        """消费确认 token（一次性）.

        Args:
            token: 确认 token

        Returns:
            原始请求信息，或 None（无效 token）
        """
        return self._confirm_tokens.pop(token, None)

    def _match_rule(
        self,
        rule: PolicyRule,
        env: str,
        action_type: ActionType | None,
        target_count: int,
    ) -> bool:
        """判断规则是否匹配.

        Args:
            rule: 策略规则
            env: 环境
            action_type: 操作类型
            target_count: 目标数量

        Returns:
            是否匹配
        """
        condition = rule.condition

        # 检查环境
        if condition.env and condition.env != env:
            return False

        # 检查操作类型
        if condition.action_type:
            if not action_type or condition.action_type != action_type.value:
                return False

        # 检查目标数量
        if condition.target_count:
            if not self._check_target_count(target_count, condition.target_count):
                return False

        return True

    def _check_target_count(self, count: int, condition: str) -> bool:
        """检查目标数量条件.

        Args:
            count: 实际数量
            condition: 条件字符串（如 ">5", ">=10"）

        Returns:
            是否满足条件
        """
        # 解析条件
        if condition.startswith(">="):
            threshold = int(condition[2:])
            return count >= threshold
        elif condition.startswith(">"):
            threshold = int(condition[1:])
            return count > threshold
        elif condition.startswith("<="):
            threshold = int(condition[2:])
            return count <= threshold
        elif condition.startswith("<"):
            threshold = int(condition[1:])
            return count < threshold
        elif condition.startswith("=="):
            threshold = int(condition[2:])
            return count == threshold
        else:
            # 默认等于
            return count == int(condition)

    def _get_target_count(self, tool_name: str, args: dict[str, Any]) -> int:
        """获取目标数量.

        Args:
            tool_name: Tool 名称
            args: 参数

        Returns:
            目标数量
        """
        if tool_name == "ssh_exec":
            return 1
        elif tool_name == "ssh_exec_batch":
            hosts = args.get("hosts", [])
            return len(hosts)
        return 0

    def _create_decision(
        self,
        rule: PolicyRule,
        env: str,
        action_type: ActionType | None,
        args: dict[str, Any],
    ) -> PolicyDecision:
        """创建策略决策.

        Args:
            rule: 触发的规则
            env: 环境
            action_type: 操作类型
            args: 参数

        Returns:
            策略决策
        """
        effect = PolicyEffect(rule.effect)

        # 生成确认 token（如果需要确认）
        confirm_token = None
        if effect == PolicyEffect.REQUIRE_CONFIRM:
            confirm_token = self._generate_confirm_token(rule, args)

        # 确定风险级别
        risk_level = "low"
        if action_type == ActionType.DESTRUCTIVE:
            risk_level = "critical" if env == "prod" else "high"
        elif action_type == ActionType.WRITE:
            risk_level = "high" if env == "prod" else "medium"

        return PolicyDecision(
            effect=effect,
            message=rule.message,
            triggered_rule=rule.name,
            confirm_token=confirm_token,
            risk_level=risk_level,
            metadata={"env": env, "action_type": action_type.value if action_type else None},
        )

    def _generate_confirm_token(self, rule: PolicyRule, args: dict[str, Any]) -> str:
        """生成确认 token.

        Args:
            rule: 规则
            args: 请求参数

        Returns:
            确认 token
        """
        import time

        token = f"conf_{secrets.token_hex(16)}"
        self._confirm_tokens[token] = {
            "rule": rule.name,
            "args": args,
            "created_at": time.time(),
        }
        return token

