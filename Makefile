.PHONY: help install dev test lint format clean run

help:  ## 显示帮助信息
	@echo "FlowPilot 开发命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装依赖
	uv sync

dev:  ## 安装开发依赖
	uv sync --all-extras

test:  ## 运行测试
	uv run pytest

coverage:  ## 运行测试并生成覆盖率报告
	uv run pytest --cov=src/flowpilot --cov-report=html --cov-report=term

lint:  ## 代码检查
	uv run ruff check src tests
	uv run mypy src

format:  ## 代码格式化
	uv run ruff format src tests

check:  ## 完整检查（格式化+检查+测试）
	make format
	make lint
	make test

clean:  ## 清理生成文件
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## 运行 CLI（开发模式）
	uv run flowpilot --help

init-config:  ## 初始化配置文件
	mkdir -p ~/.flowpilot
	cp config.example.yaml ~/.flowpilot/config.yaml
	cp .env.example .env
	@echo "配置文件已创建:"
	@echo "  ~/.flowpilot/config.yaml"
	@echo "  .env"
	@echo "请编辑这些文件填入你的配置"
