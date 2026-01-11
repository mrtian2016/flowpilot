"""AI 服务类模块"""
import json
from abc import ABC, abstractmethod

from loguru import logger

from app.schemas.ai_assistant import ToolCallResult
from .executor import ToolExecutor
from .system_prompt import create_system_prompt
from .tools_definition import TOOLS_DEFINITION, GEMINI_TOOLS_DEFINITION


class BaseAIService(ABC):
    """AI 服务基类"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def chat(
        self,
        message: str,
        history: list[dict[str, str]],
        tool_executor: ToolExecutor
    ) -> tuple[str, list[ToolCallResult]]:
        """发送消息并获取响应"""
        pass


# ============ 智谱 AI 服务 ============

class ZhipuAIService(BaseAIService):
    """智谱 AI 服务"""

    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        super().__init__(api_key, model)
        # 延迟导入
        from zai import ZhipuAiClient
        self.client = ZhipuAiClient(api_key=api_key)

    def chat(
        self,
        message: str,
        history: list[dict[str, str]],
        tool_executor: ToolExecutor
    ) -> tuple[str, list[ToolCallResult]]:
        """发送消息并获取响应"""
        # 生成系统提示词
        system_prompt = create_system_prompt(tool_executor)

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]


        # 添加历史消息
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        # 添加当前消息
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_DEFINITION,
                stream=False,
            )

            choice = response.choices[0]
            content = choice.message.content or ""
            tool_calls_result: list[ToolCallResult] = []

            # 处理工具调用
            if choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    func = tool_call.function
                    try:
                        arguments = json.loads(func.arguments) if isinstance(func.arguments, str) else func.arguments
                    except json.JSONDecodeError:
                        arguments = {}

                    result = tool_executor.execute(func.name, arguments)
                    tool_calls_result.append(ToolCallResult(
                        name=func.name,
                        arguments=arguments,
                        result=result
                    ))

                    # 将工具结果添加到内容中
                    if result.get("success"):
                        content += f"\n\n✅ {result.get('message', '操作成功')}"
                    else:
                        content += f"\n\n❌ {result.get('message', '操作失败')}"

            return content, tool_calls_result

        except Exception as e:
            logger.error(f"智谱 AI 调用失败: {e}")
            raise


# ============ Gemini 服务 ============

def _convert_proto_value(value):
    """递归转换 protobuf struct 值为 Python 原生类型"""
    logger.info(f"_convert_proto_value 输入: type={type(value)}, value={value}")

    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, dict):
        # 已经是字典，递归处理值
        return {k: _convert_proto_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        # 已经是列表，递归处理元素
        return [_convert_proto_value(v) for v in value]

    # 尝试导入 protobuf 类型
    try:
        from google.protobuf.struct_pb2 import Struct, ListValue
        if isinstance(value, Struct):
            return {k: _convert_proto_value(v) for k, v in value.fields.items()}
        elif isinstance(value, ListValue):
            return [_convert_proto_value(v) for v in value.values]
    except ImportError:
        pass

    # 处理 protobuf Value 类型
    if hasattr(value, 'HasField'):
        try:
            if value.HasField('string_value'):
                return value.string_value
            elif value.HasField('number_value'):
                return value.number_value
            elif value.HasField('bool_value'):
                return value.bool_value
            elif value.HasField('struct_value'):
                return _convert_proto_value(value.struct_value)
            elif value.HasField('list_value'):
                return _convert_proto_value(value.list_value)
            elif value.HasField('null_value'):
                return None
        except Exception as e:
            logger.warning(f"HasField 检查失败: {e}")

    # 处理 MapComposite (类似字典的 protobuf 对象)
    if hasattr(value, 'keys') and callable(value.keys):
        logger.info(f"检测到类字典对象，keys: {list(value.keys())}")
        result = {}
        for k in value.keys():
            logger.info(f"处理 key: {k}")
            result[k] = _convert_proto_value(value[k])
        return result

    # 处理可迭代对象 (类似列表的 protobuf 对象)
    if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
        try:
            logger.info(f"尝试作为可迭代对象处理")
            return [_convert_proto_value(v) for v in value]
        except Exception as e:
            logger.warning(f"迭代失败: {e}")

    # 最后尝试直接转换
    try:
        result = dict(value)
        logger.info(f"dict() 转换成功: {result}")
        return result
    except (TypeError, ValueError) as e:
        logger.warning(f"dict() 转换失败: {e}, 返回字符串")
        return str(value)


class GeminiAIService(BaseAIService):
    """Google Gemini 服务 (使用新版 google.genai SDK)"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", proxy_url: str | None = None):
        super().__init__(api_key, model)
        from google import genai
        import httpx

        http_options = {}
        if proxy_url:
            # 创建带代理的 httpx 客户端
            # 注意：google-genai SDK 内部默认使用异步客户端，对于同步 client 也会用到 httpx
            # 这里我们通过 http_options 传入自定义的 httpx_client
            # 但 genai.Client 似乎并不直接暴露 httpx_client 参数在 init 中，而是通过 http_options
            # 此时需要构造 types.HttpOptions
            
            # 简单方式：通过 api_client._httpx_client 修改 (不推荐 hack)
            # 正确方式：传入 http_options
            
            # httpx 0.28+ uses 'proxy' instead of 'proxies'
            # 禁用 SSL 验证以避免代理证书问题 ([SSL: UNEXPECTED_EOF_WHILE_READING])
            # 同时提供同步和异步客户端，因为 SDK 内部可能使用任一种
            import ssl
            # 创建不验证证书的 SSL 上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            httpx_client = httpx.Client(proxy=proxy_url, verify=ssl_context)
            httpx_async_client = httpx.AsyncClient(proxy=proxy_url, verify=ssl_context)
            
            # genai.Client 接受 http_options 参数
            # 参考 types.py HttpOptions 定义，它有 httpx_client 和 httpx_async_client 字段
            http_options = {
                "httpx_client": httpx_client,
                "httpx_async_client": httpx_async_client
            }

        self.client = genai.Client(api_key=api_key, http_options=http_options)

    def chat(
        self,
        message: str,
        history: list[dict[str, str]],
        tool_executor: ToolExecutor
    ) -> tuple[str, list[ToolCallResult]]:
        """发送消息并获取响应"""
        from google.genai import types

        logger.info("Gemini chat 开始")

        # 生成系统提示词
        system_instruction = create_system_prompt(tool_executor)
        logger.info("系统提示词生成完成")

        # 构建工具定义
        logger.info(f"GEMINI_TOOLS_DEFINITION 数量: {len(GEMINI_TOOLS_DEFINITION)}")
        try:
            tools = types.Tool(function_declarations=GEMINI_TOOLS_DEFINITION)
            logger.info("Tool 对象创建成功")
        except Exception as e:
            logger.error(f"Tool 对象创建失败: {e}")
            raise

        try:
            config = types.GenerateContentConfig(
                tools=[tools],
                system_instruction=system_instruction
            )
            logger.info("GenerateContentConfig 创建成功")
        except Exception as e:
            logger.error(f"GenerateContentConfig 创建失败: {e}")
            raise

        # 构建消息内容
        contents = []
        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))

        # 添加当前消息
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
        logger.info(f"消息内容构建完成, 共 {len(contents)} 条消息")

        try:
            logger.info("开始调用 Gemini API...")
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            logger.info("Gemini API 调用成功")

            content = ""
            tool_calls_result: list[ToolCallResult] = []

            # 处理响应
            for part in response.candidates[0].content.parts:
                if part.text:
                    content += part.text
                elif part.function_call:
                    func_call = part.function_call
                    # 调试日志：查看原始参数类型和内容
                    logger.info(f"Gemini 工具调用: {func_call.name}")
                    logger.info(f"原始 args 类型: {type(func_call.args)}")
                    logger.info(f"原始 args 内容: {func_call.args}")

                    # 使用递归转换函数处理嵌套的 protobuf 结构
                    arguments = _convert_proto_value(func_call.args) if func_call.args else {}
                    logger.info(f"转换后 arguments 类型: {type(arguments)}")
                    logger.info(f"转换后 arguments 内容: {arguments}")

                    result = tool_executor.execute(func_call.name, arguments)
                    tool_calls_result.append(ToolCallResult(
                        name=func_call.name,
                        arguments=arguments,
                        result=result
                    ))

                    # 将工具结果添加到内容中
                    if result.get("success"):
                        content += f"\n\n✅ {result.get('message', '操作成功')}"
                    else:
                        content += f"\n\n❌ {result.get('message', '操作失败')}"

            return content, tool_calls_result

        except Exception as e:
            logger.error(f"Gemini 调用失败: {e}")
            raise
