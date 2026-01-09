# FlowPilot 快速开始指南

## 1. 安装依赖

```bash
# 确保已安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync

# 或安装开发依赖
uv sync --all-extras
```

## 2. 配置环境

### 方式 1: 使用 Makefile（推荐）

```bash
make init-config
```

### 方式 2: 手动配置

```bash
# 创建配置目录
mkdir -p ~/.flowpilot

# 复制配置文件
cp config.example.yaml ~/.flowpilot/config.yaml
cp .env.example .env

# 编辑配置文件
vim ~/.flowpilot/config.yaml
vim .env
```

## 3. 配置 API Keys

编辑 `.env` 文件，填入至少一个 LLM 提供商的 API Key：

```bash
# Claude（推荐）
ANTHROPIC_API_KEY=sk-ant-xxxxx

# 或 Gemini（便宜快速）
GOOGLE_API_KEY=AIzaxxxxx

# 或 智谱（国内）
ZHIPU_API_KEY=xxxxx
```

## 4. 配置主机信息

编辑 `~/.flowpilot/config.yaml`，添加你的主机配置：

```yaml
hosts:
  my-server:
    env: staging
    user: ubuntu
    addr: your-server.com
    port: 22
    tags: [api]
```

## 5. 测试安装

```bash
# 查看帮助
uv run flowpilot --help

# 或安装后直接使用
uv pip install -e .
flowpilot --version
```

## 6. 开发命令

```bash
# 查看所有命令
make help

# 运行测试
make test

# 代码检查
make lint

# 代码格式化
make format

# 完整检查
make check
```

## 7. 下一步

- 查看 [docs.md](./docs.md) 了解完整架构设计
- 查看 [README.md](./README.md) 了解项目概览
- 开始实现 Milestone 1 的功能

## 常见问题

### Q: uv sync 报错？

确保 Python 3.12 已安装：

```bash
# 使用 pyenv 安装（推荐）
pyenv install 3.12
pyenv local 3.12

# 或检查版本
python --version  # 应该是 3.12.x
```

### Q: API Key 配置在哪里？

优先级顺序：
1. `.env` 文件（项目根目录）
2. `~/.flowpilot/.env` 文件
3. 系统环境变量

### Q: 如何切换 LLM 提供商？

```bash
# 方式 1: 命令行指定
flowpilot chat "你的请求" --provider gemini

# 方式 2: 修改配置文件
vim ~/.flowpilot/config.yaml
# 修改 llm.default_provider
```

## 开发工作流

```bash
# 1. 创建新分支
git checkout -b feature/your-feature

# 2. 开发代码
vim src/flowpilot/...

# 3. 运行测试
make test

# 4. 格式化代码
make format

# 5. 提交代码
git add .
git commit -m "feat: add your feature"
```

## 调试技巧

```bash
# 详细日志
export FLOWPILOT_LOG_LEVEL=DEBUG

# 使用 IPython 调试
uv run ipython
>>> from flowpilot.config.schema import FlowPilotConfig
>>> # 测试代码
```
