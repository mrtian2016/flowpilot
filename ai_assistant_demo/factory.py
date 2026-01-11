"""AI 服务工厂模块"""
from app.schemas.ai_assistant import AIEngine
from .services import BaseAIService, ZhipuAIService, GeminiAIService


def get_ai_service(engine: AIEngine) -> BaseAIService:
    """获取 AI 服务实例"""
    from app.core.config import settings

    if engine == AIEngine.ZHIPU:
        api_key = settings.zhipu_api_key
        if not api_key:
            raise ValueError("未配置 zhipu_api_key，请在 config.toml 中配置")
        return ZhipuAIService(api_key, settings.zhipu_model)
    elif engine == AIEngine.GEMINI:
        api_key = settings.gemini_api_key
        if not api_key:
            raise ValueError("未配置 gemini_api_key，请在 config.toml 中配置")
        return GeminiAIService(api_key, settings.gemini_model, settings.gemini_proxy_url)
    else:
        raise ValueError(f"不支持的 AI 引擎: {engine}")
