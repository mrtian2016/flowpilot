from pydantic import BaseModel, ConfigDict, Field

# ========== Host Schemas ==========

class HostCreate(BaseModel):
    """创建主机请求."""
    name: str = Field(..., description="主机别名")
    addr: str = Field(..., description="主机地址")
    user: str = Field(..., description="SSH 用户名")
    port: int = Field(22, description="SSH 端口")
    env: str = Field("dev", description="环境: dev/staging/prod")
    description: str = Field("", description="备注")
    group: str = Field("default", description="分组")
    jump: str | None = Field(None, description="跳板机别名")
    ssh_key: str | None = Field(None, description="SSH 密钥路径")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class HostUpdate(BaseModel):
    """更新主机请求."""
    addr: str | None = None
    user: str | None = None
    port: int | None = None
    env: str | None = None
    description: str | None = None
    group: str | None = None
    jump: str | None = None
    ssh_key: str | None = None
    tags: list[str] | None = None


class HostResponse(BaseModel):
    """主机响应."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    addr: str
    user: str
    port: int
    env: str
    description: str
    group: str
    jump: str | None
    ssh_key: str | None
    tags: list[str]


# ========== Host Service Schemas ==========

class HostServiceCreate(BaseModel):
    """创建主机服务请求."""
    name: str = Field(..., description="服务名称（用户友好名，如'后端服务'）")
    service_name: str = Field(..., description="服务标识（如 ir_web.service）")
    service_type: str = Field("systemd", description="服务类型: systemd, docker, pm2")
    description: str = Field("", description="服务描述")


class HostServiceUpdate(BaseModel):
    """更新主机服务请求."""
    name: str | None = None
    service_name: str | None = None
    service_type: str | None = None
    description: str | None = None


class HostServiceResponse(BaseModel):
    """主机服务响应."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    host_id: int
    host_name: str  # 额外返回主机名
    name: str
    service_name: str
    service_type: str
    description: str


# ========== Jump Schemas ==========

class JumpCreate(BaseModel):
    """创建跳板机请求."""
    name: str
    addr: str
    user: str
    port: int = 22


class JumpResponse(BaseModel):
    """跳板机响应."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    addr: str
    user: str
    port: int


# ========== Service Schemas ==========

class ServiceCreate(BaseModel):
    """创建服务请求."""
    name: str
    description: str = ""
    config_json: dict = Field(default_factory=dict)


class ServiceResponse(BaseModel):
    """服务响应."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    config_json: dict


# ========== Policy Schemas ==========

class PolicyCreate(BaseModel):
    """创建策略请求."""
    name: str
    condition: dict
    effect: str = "require_confirm"
    message: str = ""


class PolicyResponse(BaseModel):
    """策略响应."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    condition: dict
    effect: str
    message: str


# ========== Audit Schemas ==========

class AuditSessionResponse(BaseModel):
    """审计会话响应."""
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    timestamp: str
    user: str
    input: str
    status: str
    provider: str | None
    total_duration_sec: float | None
