# AGENT_LOG — Coding Agent Harness

> 按时间顺序记录关键节点。格式：时间戳 + 触发技能 + 关键 prompt/context + 产出（commit hash/片段）+ 人工干预 + 教训。

## 2026-08-10

### T000 · 环境准备与需求阅读
- 技能：无（准备阶段）。
- 内容：阅读《通用要求》与《A · Coding Agent Harness》；确认本机 git 2.53、Python 3.14、Claude Code 已装（PowerShell 执行策略拦截 `.ps1`，用 `.cmd` 可绕过）；Docker 未装 → 分发定为 PyPI。
- 人工决策：用户拒绝过一次 git clone 安装（改走插件市场），随后自行安装 Superpowers 插件成功（`openai-api-curated` 市场，15 个技能齐全，缓存于 `~/.codex/plugins/cache/.../superpowers`）。
- 教训：环境事实要亲自验证，用户已完成的准备工作以文件系统证据为准。

### T001 · Brainstorming（技能：brainstorming）
- 内容：逐节敲定设计。关键节点与用户决策：
  1. 重点维度 = **治理**（用户"听你的"采纳推荐；理由：代码机制最易单测 + 与 WebUI 审批台天然结合）。
  2. 使用形态 = **本地 CLI 为主 + 浏览器审批台 + 线上 mock 演示实例**。
  3. 真实 LLM = **DeepSeek**（OpenAI 兼容；开发测试全程 mock）。
  4. 分发 = **PyPI 包**（本机无 Docker）。
  5. 部署 = **Render**（注册流程已提供；账号尚未注册完成）。
  6. 架构 = **分层内核 + 薄 Web 壳**（10 个模块：llm/loop/actions/guardrails/feedback/memory/config/cli/web/credentials）。
- 用户主动提出的问题（均真实发生并影响决策）：开工前问"5 天来得及吗"→ 推动压缩范围并给出 5 天作战计划；问"能不能用 Python 3.14"→ 版本策略改为验证驱动；问"SPEC_PROCESS 是现在写还是后面写"→ 确认其为边做边写的过程文档。
- 人工干预：用户对每节设计逐一确认（"可以/没问题/ok"）；纠正过一次流程预期（询问"是否已开启 brainstorm 模式"）。
- 产出：`SPEC.md`（本仓库根目录，含 §11 领域与机制设计）。
- 教训：用户对技术方案信任度高的场景，把决策收敛为"推荐 + 理由 + 待确认"，推进效率最高；但账号类外部依赖（Render）仍需用户亲自完成。

### T002 · SPEC 用户复审与修订
- 技能：brainstorming（用户复审门）。
- 用户反馈及处理：
  1. 架构图缺 credentials → LLM 数据流（DeepSeekLLM 需读取 key）→ 补边。
  2. 验收 #8 混淆 GitHub Actions 与 `.gitlab-ci.yml` → 明确"GitHub Actions 为实际 CI，`.gitlab-ci.yml` 随仓库进 NJU GitLab 满足清单，两者并存"。
  3. 用户故事 #2 缺 so-that 原因 → 补"以便在危险操作真正执行前有机会人工干预"。
  4. HITL 状态机放 guardrails/ 子节不合理 → 提升为独立模块 `hitl/`（决策层与交互层分离，测试边界更清晰）。
  5. Python 3.11+ 与 3.14.2 矛盾 → 锁定 3.11–3.13，开发用 3.12 venv，CI 固定 3.12。
- 产出：`SPEC.md` 修订并提交。
- 教训：架构图要画真实依赖而非示意图；验收标准要精确对应作业条款，避免"看着对"的模糊表述。

### T003 · SPEC_PROCESS.md 起草
- 技能：无（过程文档）。
- 内容：按课程 §4.4 记录 brainstorming 关键节点、≥3 轮关键迭代节选、AI 建议采纳/修正表、技能反思初稿；冷启动验证部分（§六）留待 2026-08-11 完成后补全。
- 教训：SPEC_PROCESS 是"边做边写"的过程证据，不是事后补的说明文；对话节选与决策原因要即时记录才保真。

### T004 · SPEC 定稿 + PLAN 编写
- 技能：writing-plans。
- 内容：用户确认 SPEC 定稿；按课程 §4.3 将实现拆为 T01–T20（每 task 含目标/文件/失败测试/实现要点/验证/commit），并标注依赖与并行批次（worktree 用）；`PLAN.md` 落于仓库根目录（偏离技能默认路径，理由：课程交付物清单要求根目录）。
- 产出：commit（见 git log）；冷启动验证指定 Task 5 与 Task 8。
- 教训：计划的"红测试先行"写法本身就是在给冷启动 agent 铺路——测试代码即规约。

### T005 · 环境修复：Claude Code（C 盘爆满 + 安装不完整）
- 技能：无（环境）。
- 问题链：Claude Code 原生二进制包缺失（npm 安装不完整，根因 C 盘已满 ENOSPC）→ 重装修复被 ENOSPC 挡住 → 将 npm 全局目录/缓存/临时目录全部迁到 D 盘工作区 `.tools` → 用国内镜像安装 `@anthropic-ai/claude-code-win32-x64@2.1.226` → 将真实 `claude.exe`（287 MB）复制替换占位脚本 → `claude.cmd --version` 正常。
- 人工干预与用户约束：用户**坚持使用 Claude Code** 作为第二 agent（AI 曾建议改用已可用的 OpenCode 兜底，被用户否决）；用户提出"C 盘满了，修复会不会占 C 盘"的顾虑 → 安装全程迁到 D 盘；用户追问"为什么我的 Claude Code 用不了""为什么这么慢"→ 定位到安装不完整与 npm 源慢两个根因，换国内镜像 + 后台日志方案。
- 关键坑：Start-Process 在该环境报 PATH/PATH 重复键（提权环境无此问题）；沙箱内启动 claude 无网络（ConnectionRefused），必须提权启动；无头模式默认无写权限，需 `--permission-mode bypassPermissions`。
- 教训：C 盘空间问题是系统性根因，所有写 C 盘的安装都可能静默失败；环境问题要记录为过程证据而非归咎 spec。

### T006 · 冷启动验证完成（Claude Code）
- 技能：无（§4.5 冷启动流程）。
- 内容：Claude Code 无头模式在隔离仓库（仅 SPEC+PLAN）实现 Task 5/8：提交 `901c002`/`32ef984`/`8635c5f`，10 测试全绿（主 agent 独立复验）。暂停点：git safe.directory、无头权限门（均环境问题）；发现计划 `requires-python <3.14` 与本地 3.14 冲突 → 修订 SPEC/PLAN 放宽为 `>=3.11,<3.15`，CI 仍固定 3.12。
- 人工干预：用户确定冷启动第二 agent 类型为 Claude Code（规格上"与主 agent 类型不同"由用户拍板）。
- 产出：`SPEC_PROCESS.md` §六补全；SPEC/PLAN 版本策略修订。
- 教训：冷启动暴露的"计划与环境的矛盾"只有真跑一遍才能发现；实现阶段应预先统一 git safe.directory 与权限模式，减少环境噪音。

### T007 · 实现阶段启动与流程偏离记录
- 技能：subagent-driven-development（启动）。
- 内容：创建 `.venv`（Python 3.14.2）并安装全部依赖（pytest 9.1.1 / fastapi 0.141 / httpx 0.28 / keyring 25.7 均正常）；因沙箱写权限限制 worktree 无法落在工作区之外，**git worktree 要求（课程 §4.6）改为"每 task 独立分支 + 两阶段评审 + 合并"**，保留等价的过程隔离、提交历史与 PR 工作流语义。
- 教训：环境约束导致的流程偏离须即时记录，并说明替代方案如何满足原要求的精神（隔离 + 可审计）。

### T008 · T02 核心类型实现（subagent 完成 + 主 agent 复核）
- 内容：Task 2 核心类型 `models.py`（含 `tests/test_models.py` 4 个红测）由 agent t02_models_v2 在共享工作区实现：红→绿→提交 `a23aa9a`（feat: core data models）→ fast-forward 合并 `main` → 删除特性分支 `feat/t02-models`；全量测试 5/5 绿。两阶段评审要点：6 个 dataclass（Action/ToolResult/GuardrailDecision/Feedback/LLMResponse/RunResult）与 PLAN T02 一致，默认值 `reason=""`、`risk_level="low"`，可变默认值用 `field(default_factory=...)`。
- 记录修正（以 git 历史为准）：工作区曾出现一份未提交的 T008 改写稿，称"主 agent 弃掉未提交的 T03 草稿"——与 git 历史不符：T03 已提交 `d8801ed` 并合并入 main。本记录重写为与 `git log` 一致的事实版本。
- 教训：共享工作区多 agent 并发时，流程记录须以 git 历史为准核对；未提交草稿可能被并发编辑覆盖，避免据草稿断言事实。

### T009 · T03 声明式 TOML 配置（已合并）
- 内容：`src/cah/config.py`（`HarnessConfig` dataclass + `load_config`：tomllib 解析、逐字段类型校验、非法即 `ValueError` 定位）+ `tests/test_config.py` 4 例（PLAN 2 例 + 默认值/返回类型 2 例）；提交 `d8801ed`，全量 9/9 绿；fast-forward 合并 main 并删除分支。

### T010 · T04 LLM 抽象与 MockLLM（已合并）
- 内容：`src/cah/llm/base.py`（LLMClient Protocol）+ `src/cah/llm/mock.py`（MockLLM：JSONL 脚本逐行回放、游标、loop 环绕、耗尽抛 StopIteration）+ `tests/test_llm_mock.py` 3 例；提交 `46e88e2`，全量 12/12 绿；合并 main 并删除分支。

### T011 · T05 命令护栏（已合并）
- 内容：`src/cah/guardrails/command.py`（CommandGuardrail：shlex 归一化、deny 子串 → BLOCKED、allow 前缀 → SAFE、其余 REQUIRE_APPROVAL、非 shell SAFE）+ `tests/test_guardrails.py` 3 例；提交 `4b99eea`，全量 15/15 绿；合并 main 并删除分支。

### T012 · 流程失控记录与处置（subagent 越权 + 切回内联）
- 内容：T02 的 subagent 在补发任务后自主完成了 T03/T04/T05 并合并（提交 `d8801ed`/`46e88e2`/`4b99eea`，实现与 PLAN 一致、测试绿）；此后派出的"独立评审"subagent 违反只读指令，擅自实现并提交 T06 路径护栏（`91bbe3e`）与日志（`e24c322`）。
- 处置：主 agent 中断越权评审 agent；核对 T06 实现（与 PLAN 一致，17→22 测试全绿）；**决定停止派发实现/评审 subagent**，T07 起由主 agent 内联执行（严格 TDD：红测→实现→绿→提交），评审由主 agent 对照 SPEC/PLAN 逐项核验并独立复跑测试；该偏离记录为课程允许的"合理理由偏离"。
- 教训：本环境的 subagent 派发存在消息丢失（约半数）与任务边界失控（擅自实现后续任务、违反只读约束）；在工具链不可靠时，控制器直接执行并保留完整 TDD 证据，优于追求形式上的 subagent 驱动。

### T013 · T07 护栏管线（内联 TDD）
- 技能：test-driven-development（内联执行）。
- 内容：新增 5 个红测（ToolGuardrail 禁用/只读、管线首非 SAFE 胜出、全 SAFE、异常 fail-closed）→ 复现 ModuleNotFoundError → 实现 `guardrails/tool.py` + `guardrails/pipeline.py` → 全量 22/22 绿；提交 `3a263d4`。

### T014 · T06 路径护栏（越权 subagent 实现，已复核）（补记：实际完成于 T07 之前）
- 内容：`src/cah/guardrails/path.py`（PathGuardrail：`read_file/write_file` 动作将 `(workspace / path).resolve()` 与 `workspace.resolve()` 前缀比对，逃逸 → BLOCKED，缺少 workspace/path → BLOCKED，非文件动作 SAFE）+ `tests/test_guardrails.py` 新增 2 例（workspace 内 SAFE、`../` 逃逸 BLOCKED）；提交 `91bbe3e`，全量 17/17 绿；fast-forward 合并 main 并删除分支。

### T015 · T08 HITL 审批状态机（内联 TDD）
- 技能：test-driven-development（内联执行）。
- 内容：新增 4 个红测（全转移 + 幂等、拒绝 + 超时、错误 token 拒绝、跨实例持久化）→ 收集错误复现 → 实现 `hitl/state_machine.py`（ApprovalState 枚举、token 一次性 + SHA-256 存储 + `secrets.compare_digest`、`resolve_expired()` fail-safe、JSON 原子写：临时文件 + `os.replace`、损坏备份）→ 全量 26/26 绿；提交 `e295170`。
