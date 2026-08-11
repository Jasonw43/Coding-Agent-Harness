# Coding Agent Harness (`cah`)

AI4SE 期末项目 · A · Coding Agent Harness。一个治理优先的编码智能体 harness：把"只会产生下一步设想"的 LLM 封装成一台稳定、可治理、可离线验证的编码系统。**Agent = LLM + Harness**，本仓库交付的是 harness 内核本身。

## 项目简介

`cah` 由你自己实现的主循环驱动：组装上下文 → 调用 LLM → 解析动作 → 治理护栏（含 HITL 人工审批）→ 工具执行 → 客观反馈 → 回灌 → 停机判断。六个维度（决策 / 工具 / 治理 / 反馈 / 记忆 / 配置）都有可运行实现，其中**治理**是主要贡献：分级护栏（命令黑/白名单 + 路径沙箱 + 工具策略）、逻辑沙箱、HITL 审批状态机。

核心纪律：**移除真实 LLM 后，每个机制仍可用 mock/stub LLM 写出确定性单元测试**。全部测试离线可跑（`pytest`，不依赖网络）。

## 安装

要求：Python 3.11–3.14（CI 固定 3.12）。

```bash
# 方式一：从 PyPI（发布后）
pip install cah

# 方式二：直接从 GitHub 仓库安装
pip install git+https://github.com/Jasonw43/Coding-Agent-Harness.git

# 开发模式（含测试依赖）
git clone https://github.com/Jasonw43/Coding-Agent-Harness.git
cd Coding-Agent-Harness
pip install -e ".[dev]"
```

## 运行

```bash
# 用 mock LLM 跑一次端到端任务（确定性、不联网、不花钱）
cah run --mock "write a note"

# 跑机制演示（护栏拦截 / 反馈闭环 / HITL 状态机）
cah demo

# 用真实 LLM（DeepSeek）运行——先配置 key（见下）
cah key set
cah run "实现一个函数并补测试"

# HITL 审批与状态查看
cah status
cah approve <action-id> --token <token>
cah reject <action-id> --token <token>

# 配置管理
cah config init
cah config show
```

Web 审批台（demo 模式，mock LLM + 只读沙箱）：

```bash
HARNESS_DEMO=1 uvicorn cah.web.app:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000`，点击"启动演示运行"，即可看到 agent 尝试危险动作、等待人工审批的完整流程。

## Key 安全配置

`cah` 的 API key **绝不硬编码、绝不提交 git、绝不写日志**。

```bash
cah key set      # 隐藏输入，存储到操作系统凭据管理器（Windows Credential Manager）
cah key status   # 只显示掩码状态，不回显明文
cah key clear    # 清除
```

存储优先级：**OS 凭据管理器（keyring）> 环境变量（`CAH_API_KEY`）> `.env` 文件**。

风险说明：`.env` 为明文文件且进程环境可见，仅作为无凭据管理器环境的兜底；`.env` 已在 `.gitignore` 中排除。真实 LLM 需要有效 key；不配置 key 时请使用 `--mock`。真实模式下模型按 JSON 动作协议输出（如 `{"action": {"type": "write_file", "params": {...}}}`），harness 解析后经护栏执行，复杂多步任务的效果取决于模型遵循协议的程度。

## 分发（PyPI 包）

```bash
python -m build          # 产出 dist/*.whl 与 sdist
pip install dist/*.whl   # 本地验证
```

CI（GitHub Actions + GitLab CI `unit-test` job）在每次 push 时运行测试并构建 wheel。

## 目录结构

```
SPEC.md / PLAN.md / SPEC_PROCESS.md / AGENT_LOG.md / REFLECTION.md
src/cah/
  models.py         # 核心数据类型
  config.py         # TOML 声明式配置
  llm/              # LLM 抽象：MockLLM（确定性）+ DeepSeekLLM
  loop/agent.py     # 主循环（上下文→LLM→动作→护栏→工具→反馈→停机）
  actions/          # 工具注册表 + 工作区沙箱（读写文件/shell/测试/搜索/记忆）
  guardrails/       # 命令护栏 / 路径护栏 / 工具护栏 / 管线（fail-closed）
  hitl/             # HITL 审批状态机（JSON 持久化、token 一次性）
  feedback/         # 确定性校验器（测试输出→结构化反馈）
  memory/           # 跨会话记忆（按需召回）
  credentials/      # keyring 优先的凭据管理
  cli.py / web/     # CLI 入口 + FastAPI 审批台
tests/              # 全部 mock-LLM 确定性单元测试
demo/mechanism_demo.py  # 三个必需行为的机制演示
```

## 安全边界

- **路径沙箱**：所有文件读写解析后必须位于工作区内，`../` 与符号链接逃逸一律拦截。
- **命令护栏**：黑名单（`rm -rf`、`DROP DATABASE`、`git push`、`curl|sh`、`sudo` 等）+ 白名单前缀；未匹配命令默认转人工审批。
- **只读模式**：`--read-only` / demo 模式禁用写文件与 shell。
- **fail-closed**：护栏自身出错时按拒绝处理。
- **HITL**：危险动作进入 `PENDING`，人工批准/拒绝/超时（超时默认拒绝）；一次性 token + SHA-256 存储。

## 已知限制

- Python 3.11–3.14；CI 固定 3.12 作为稳定基线。
- 真实 LLM 支持 DeepSeek（OpenAI 兼容）；工具调用通过 JSON 动作协议 + 解析器实现（`cah/actions/parser.py`），已被确定性测试覆盖。
- 线上 demo 实例为 mock + 只读模式，用于演示审批流，不执行真实代码变更。
- Render 免费档闲置 15 分钟休眠，首次访问需约 30–60 秒冷启动。
- Windows 下 `shell` 工具使用系统默认解释器（cmd），命令 token 化按跨平台语义实现。

## 第三方依赖

- `httpx` (BSD-3-Clause)、`fastapi` / `uvicorn` (MIT)、`keyring` (MIT)、`pytest` (MIT)、`hatchling` (MIT)。
- 完整许可证文本见各依赖发行包。
