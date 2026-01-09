# FlowPilot

> AI Agent for programmer workflow automation

FlowPilot 是一个面向程序员的智能工作流自动化工具，通过 AI Agent 理解自然语言指令，自动执行日常运维任务。

## ✨ 核心特性

- 🤖 **多 LLM 支持**：支持 Claude、Gemini、智谱（GLM），自动路由或手动切换
- 🔧 **SSH 自动化**：通过别名快速连接，支持跳板机、批量执行
- 📊 **日志分析**：智能拉取和分析服务日志，提取关键信息
- ☸️ **K8s 集成**：查询 Pod 状态、日志、事件（可选）
- 🔒 **安全策略**：生产环境操作强制确认，防止误操作
- 📝 **完整审计**：所有操作记录可追溯，自动生成报告

## 🚀 快速开始

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/flowpilot
cd flowpilot

# 2. 安装依赖（使用 uv）
uv sync

# 3. 激活虚拟环境
source .venv/bin/activate

# 4. 安装为可执行命令
uv pip install -e .
```

### 配置

```bash
# 1. 创建配置目录
mkdir -p ~/.flowpilot

# 2. 复制示例配置
cp config.example.yaml ~/.flowpilot/config.yaml

# 3. 配置 API Keys
cp .env.example .env
# 编辑 .env，填入你的 API Keys
```

### 使用

```bash
# 查看版本
flowpilot --version

# 初始化配置
flowpilot init

# 自然语言执行（开发中）
flowpilot chat "查看 prod-api-3 的运行时间"
flowpilot chat "排查 payment 服务在生产环境的错误"

# 指定 LLM 提供商
flowpilot chat "查看日志" --provider gemini

# 查看历史
flowpilot history --last 10

# 配置管理
flowpilot config show
flowpilot config validate
```

## 🏗️ 技术栈

- **语言**: Python 3.12
- **包管理**: uv
- **数据库**: SQLite
- **LLM**: Claude / Gemini / 智谱（多提供商）
- **CLI**: Typer + Rich
- **配置**: Pydantic + YAML

## 📁 项目结构

```
flowpilot/
├── src/flowpilot/
│   ├── agent/           # LLM Provider 抽象层
│   ├── tools/           # MCP Tools (SSH/Logs/K8s)
│   ├── policy/          # 策略引擎
│   ├── config/          # 配置管理
│   ├── audit/           # 审计日志
│   ├── cli/             # CLI 入口
│   └── utils/           # 工具函数
├── tests/               # 测试
├── docs.md              # 完整 PRD 文档
├── config.example.yaml  # 配置示例
└── pyproject.toml       # 项目配置
```

## 🛠️ 开发

```bash
# 安装开发依赖
uv sync --all-extras

# 运行测试
pytest

# 代码格式化
ruff format

# 代码检查
ruff check
mypy src
```

## 📖 文档

详细设计文档请查看 [docs.md](./docs.md)

## 🗺️ 开发路线

- [x] 项目初始化和架构设计
- [ ] **Milestone 1**: 最小 Agent 循环（2-3周）
  - [ ] LLM Provider 抽象层
  - [ ] ssh_exec Tool
  - [ ] Policy Engine
  - [ ] CLI 基础框架
- [ ] **Milestone 2**: 多 Tools + 多步规划（1-2周）
- [ ] **Milestone 3**: K8s + Report + 优化（1-2周）

## 📝 License

MIT

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**注意**: 当前处于早期开发阶段，API 可能会发生变化。
