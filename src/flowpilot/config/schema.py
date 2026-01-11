"""配置 Schema 定义（使用 Pydantic）."""

from typing import Any

from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置."""

    model: str = Field(..., description="模型名称")
    api_key_env: str = Field(..., description="API Key 环境变量名")
    max_tokens: int = Field(default=4096, description="最大 token 数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")


class RoutingRule(BaseModel):
    """场景路由规则."""

    scenario: str = Field(..., description="场景名称")
    provider: str = Field(..., description="提供商名称")
    model: str | None = Field(None, description="可选：覆盖模型")
    condition: dict[str, Any] | None = Field(None, description="路由条件")


class LLMConfig(BaseModel):
    """LLM 配置."""

    default_provider: str = Field(default="claude", description="默认提供商")
    providers: dict[str, LLMProviderConfig] = Field(..., description="提供商配置")
    routing: list[RoutingRule] = Field(default_factory=list, description="路由规则")


class HostConfig(BaseModel):
    """主机配置."""

    env: str = Field(..., description="环境: dev/staging/prod")
    user: str = Field(..., description="SSH 用户名")
    addr: str = Field(..., description="主机地址")
    port: int = Field(default=22, description="SSH 端口")
    jump: str | None = Field(None, description="跳板机别名")
    tags: list[str] = Field(default_factory=list, description="主机标签")
    ssh_key: str | None = Field(None, description="SSH 密钥路径")
    # 新增：中文友好字段
    description: str = Field(default="", description="中文备注/描述")
    group: str = Field(default="default", description="分组名称")



class JumpConfig(BaseModel):
    """跳板机配置."""

    addr: str = Field(..., description="跳板机地址")
    user: str = Field(..., description="用户名")
    port: int = Field(default=22, description="端口")


class ServiceLogsConfig(BaseModel):
    """服务日志配置."""

    path: str = Field(..., description="日志文件路径")
    format: str = Field(default="text", description="日志格式: json/text")


class ServiceK8sConfig(BaseModel):
    """服务 K8s 配置."""

    selector: str = Field(..., description="Pod selector")
    namespace: dict[str, str] = Field(..., description="环境对应的 namespace")


class ServiceConfig(BaseModel):
    """服务配置."""

    description: str = Field(default="", description="服务描述")
    hosts: dict[str, list[str]] = Field(..., description="环境对应的主机列表")
    logs: ServiceLogsConfig | None = Field(None, description="日志配置")
    k8s: ServiceK8sConfig | None = Field(None, description="K8s 配置")
    healthcheck: dict[str, Any] | None = Field(None, description="健康检查配置")


class PolicyCondition(BaseModel):
    """策略条件."""

    env: str | None = Field(None, description="环境限制")
    action_type: str | None = Field(None, description="操作类型")
    target_count: str | None = Field(None, description="目标数量条件")


class PolicyRule(BaseModel):
    """策略规则."""

    name: str = Field(..., description="规则名称")
    condition: PolicyCondition = Field(..., description="触发条件")
    effect: str = Field(..., description="效果: allow/require_confirm/deny")
    message: str = Field(..., description="提示消息")


class FlowPilotConfig(BaseModel):
    """FlowPilot 主配置."""

    llm: LLMConfig = Field(..., description="LLM 配置")
    hosts: dict[str, HostConfig] = Field(default_factory=dict, description="主机配置")
    jumps: dict[str, JumpConfig] = Field(default_factory=dict, description="跳板机配置")
    services: dict[str, ServiceConfig] = Field(
        default_factory=dict, description="服务配置"
    )
    policies: list[PolicyRule] = Field(default_factory=list, description="策略规则")
