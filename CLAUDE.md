# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

FlowPilot 是一个 Python 3.12 的 AI 驱动程序员工作流自动化工具，通过自然语言指令自动执行 DevOps 和运维任务。

## 开发命令

```bash
# 安装依赖
uv sync                      # 基础依赖
uv sync --all-extras         # 全部依赖（含开发工具）

# 运行测试
make test                    # 或 uv run pytest

# 代码检查
make lint                    # ruff check + mypy

# 代码格式化
make format                  # ruff format

# 完整检查（格式化+检查+测试）
make check

# 运行单个测试文件
uv run pytest tests/unit/test_config.py

# 运行单个测试函数
uv run pytest tests/unit/test_config.py::test_function_name -v

# 生成覆盖率报告
make coverage

# 运行 CLI
uv run flowpilot --help

# 启动 MCP Server
uv run flowpilot serve              # 默认端口 8765
uv run flowpilot serve -p 9000      # 自定义端口
uv run flowpilot serve --reload     # 开发模式
```

## 架构概览

```
src/flowpilot/
├── agent/           # LLM Provider 抽象层（多提供商支持）
│   ├── base.py      # LLMProvider 基类
│   ├── claude.py    # Claude Provider
│   ├── gemini.py    # Gemini Provider
│   ├── zhipu.py     # 智谱 GLM Provider
│   ├── router.py    # Provider 路由器
│   └── executor.py  # Tool 执行器
├── tools/           # MCP Tools（遵循 Model Context Protocol）
│   ├── base.py      # MCPTool 基类 & 工具注册表
│   ├── ssh.py       # SSH 命令执行
│   └── config.py    # 配置管理
├── mcp/             # MCP Server（FastAPI + SSE）
│   ├── server.py    # FastAPI 主应用
│   ├── protocol.py  # MCP 协议消息定义
│   ├── sse.py       # SSE 传输层
│   ├── registry.py  # Tools/Resources/Prompts 注册
│   └── handlers/    # 请求处理器
├── policy/          # 策略引擎（安全检查）
│   ├── engine.py    # 策略决策引擎
│   └── action_classifier.py  # 命令风险分类
├── audit/           # 审计日志系统
├── config/          # 配置管理（Pydantic Schema）
├── core/            # 数据模型（SQLAlchemy ORM）
├── cli/             # Typer CLI 入口
└── utils/           # 工具函数
```

## 核心工作流

```
用户输入 → LLM 理解意图 → Tool Calls → PolicyEngine 安全检查
→ 生产环境需确认 → ToolExecutor 执行 → AuditLogger 记录 → LLM 分析结果
```

## 关键约定

- **异步优先**：所有 LLM 调用和工具执行使用 `async/await`
- **严格类型检查**：MyPy 启用 `strict = true`，所有函数必须有类型注解
- **Tool 返回 ToolResult**：包含 status, output, error, exit_code, duration_sec
- **敏感信息过滤**：使用 `utils/sensitive.py` 的 `mask_sensitive()` 过滤 API Key、密码

## 代码风格

- Ruff 格式化：100 字符行长，双引号
- 遵循 PEP 8，使用 isort 排序 import
- 类型注解必须完整（disallow_untyped_defs）

## 配置文件

- `~/.flowpilot/config.yaml`：主配置文件
- `.env`：API Keys 等敏感配置
- `config.example.yaml`：配置示例
