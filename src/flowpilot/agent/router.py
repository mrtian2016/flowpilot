"""Provider 路由器，根据配置选择 LLM."""

import os
from typing import Any

from ..config.schema import FlowPilotConfig, LLMConfig
from .base import LLMProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .zhipu import ZhipuProvider


class ProviderRouter:
    """LLM Provider 路由器."""

    def __init__(self, config: LLMConfig) -> None:
        """初始化路由器.

        Args:
            config: LLM 配置
        """
        self.config = config
        self._providers: dict[str, LLMProvider] = {}

    def get_provider(
        self, provider_name: str | None = None, scenario: str | None = None
    ) -> LLMProvider:
        """获取 LLM Provider 实例.

        Args:
            provider_name: 指定提供商名称（覆盖自动路由）
            scenario: 场景名称（用于自动路由）

        Returns:
            LLM Provider 实例

        Raises:
            ValueError: 提供商不存在或配置错误
        """
        # 1. 确定使用哪个 provider
        selected_provider = self._route(provider_name, scenario)

        # 2. 创建或复用实例
        if selected_provider not in self._providers:
            self._providers[selected_provider] = self._create_provider(selected_provider)

        return self._providers[selected_provider]

    def _route(self, provider_name: str | None, scenario: str | None) -> str:
        """路由逻辑：选择 Provider.

        Args:
            provider_name: 指定的提供商
            scenario: 场景名称

        Returns:
            提供商名称
        """
        # 优先级 1：明确指定
        if provider_name:
            if provider_name not in self.config.providers:
                raise ValueError(
                    f"提供商 '{provider_name}' 未配置。" f"可用的提供商: {list(self.config.providers.keys())}"
                )
            return provider_name

        # 优先级 2：场景路由
        if scenario and self.config.routing:
            for rule in self.config.routing:
                if rule.scenario == scenario:
                    return rule.provider

        # 优先级 3：默认提供商
        return self.config.default_provider

    def _create_provider(self, name: str) -> LLMProvider:
        """创建 Provider 实例.

        Args:
            name: 提供商名称

        Returns:
            Provider 实例

        Raises:
            ValueError: 未知的提供商或配置错误
        """
        if name not in self.config.providers:
            raise ValueError(f"提供商 '{name}' 未配置")

        provider_config = self.config.providers[name]

        # 从环境变量获取 API Key
        api_key = os.getenv(provider_config.api_key_env)
        if not api_key:
            raise ValueError(
                f"{'提供商'} '{name}' 的 API Key 未设置。"
                f"请设置环境变量: {provider_config.api_key_env}"
            )

        # 根据 name 创建对应的 Provider
        match name:
            case "claude":
                return ClaudeProvider(
                    api_key=api_key,
                    model=provider_config.model,
                    max_tokens=provider_config.max_tokens,
                    temperature=provider_config.temperature,
                )
            case "gemini":
                return GeminiProvider(
                    api_key=api_key,
                    model=provider_config.model,
                    max_tokens=provider_config.max_tokens,
                    temperature=provider_config.temperature,
                )
            case "zhipu":
                return ZhipuProvider(
                    api_key=api_key,
                    model=provider_config.model,
                    max_tokens=provider_config.max_tokens,
                    temperature=provider_config.temperature,
                )
            case _:
                raise ValueError(
                    f"未知的提供商: {name}。" f"支持的提供商: claude, gemini, zhipu"
                )

    def list_providers(self) -> list[str]:
        """列出所有可用的提供商.

        Returns:
            提供商名称列表
        """
        return list(self.config.providers.keys())
