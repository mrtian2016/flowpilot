"""AI 助手服务模块

支持智谱 AI 和 Google Gemini 两种 AI 引擎，
通过工具调用实现规则的创建和管理。
"""
from .executor import ToolExecutor
from .services import BaseAIService, ZhipuAIService, GeminiAIService
from .factory import get_ai_service
from .tools_definition import TOOLS_DEFINITION, GEMINI_TOOLS_DEFINITION
from .system_prompt import SYSTEM_PROMPT_TEMPLATE, create_system_prompt

__all__ = [
    "ToolExecutor",
    "BaseAIService",
    "ZhipuAIService",
    "GeminiAIService",
    "get_ai_service",
    "TOOLS_DEFINITION",
    "GEMINI_TOOLS_DEFINITION",
    "SYSTEM_PROMPT_TEMPLATE",
    "create_system_prompt",
]
