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
