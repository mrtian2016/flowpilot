# FlowPilot 快速开始指南

## 前提条件

- Python 3.12+
- uv 包管理器
- 至少一个 LLM API Key（Claude/Gemini/智谱）

## 安装步骤

### 1. 克隆并安装

```bash
cd /Users/tianjy/flowpilot

# 同步依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate

# 安装为可执行命令
uv pip install -e .
```

### 2. 初始化配置

```bash
flowpilot init
```

这会创建 `~/.flowpilot/config.yaml` 配置文件。

### 3. 配置 API Keys

编辑 `~/.bashrc` 或 `~/.zshrc`，添加：

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
export ZHIPU_API_KEY="..."
```

然后重新加载：

```bash
source ~/.zshrc
```

### 4. 编辑配置文件

编辑 `~/.flowpilot/config.yaml`，添加你的主机配置。

### 5. 验证配置

```bash
flowpilot config validate
```

## 基本使用

### 自然语言交互

```bash
# 基础命令
flowpilot chat "查看服务器运行时间"

# 指定 Provider
flowpilot chat "查看磁盘使用" --provider claude

# Dry-run 模式
flowpilot chat "删除临时文件" --dry-run
```

### 查看历史

```bash
flowpilot history --last 10
```

### 生成报告

```bash
flowpilot report <session_id>
```

### 配置管理

```bash
flowpilot config show
flowpilot config validate
```

## 运行测试

```bash
# 所有测试（56 个）
.venv/bin/python -m pytest tests/unit/ -v

# 生成覆盖率报告
.venv/bin/python -m pytest tests/unit/ --cov=src/flowpilot
```

✅ **所有 56 个单元测试通过！**

# 或检查版本
python --version  # 应该是 3.12.x

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
