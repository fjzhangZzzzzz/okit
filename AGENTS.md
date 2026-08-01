# 仓库开发规范

<!-- codebase-memory-mcp:start -->
# 代码库知识图谱（codebase-memory-mcp）

本项目使用 codebase-memory-mcp 维护代码知识图谱。进行代码发现时优先使用图谱工具，而不是 grep、glob 或文件搜索。

优先顺序：

1. `search_graph`：按模式查找函数、类、路由和变量；
2. `trace_path`：追踪调用方或被调用方；
3. `get_code_snippet`：读取指定函数或类的源码；
4. `query_graph`：对复杂关系执行 Cypher 查询；
5. `get_architecture`：获取项目架构概览。

仅在搜索字符串字面量、错误消息、配置值、非代码文件，或图谱结果不足时回退到 grep/glob/file-search。
<!-- codebase-memory-mcp:end -->

以下规则适用于本仓库的所有变更。

## 开发与发布流程

- 本项目为个人开发和使用，采用 `main` 单分支开发与发布；日常开发可直接提交并推送到 `main`。
- 每个提交必须通过 CI 中必要的构建和测试；CI 未通过不得发布制品。
- 不要求创建开发分支或 Pull Request。提交仍应聚焦一个可独立理解的变更。
- 发布有预发布与正式两个通道：日常测试使用预发布通道，可按需要频繁发布；达到阶段性目标且验证无误后，将同一 commit 的预发布制品升格为正式版本。

## 提交消息与分支命名

- 提交消息使用 `<type>(<scope>): <中文摘要>` 格式；`scope` 可省略，但涉及 Issue 时在末尾附 `(#<编号>)`。
- `type` 使用仓库既有约定：`feat` 表示新增能力，`fix` 表示修复，`refactor` 表示不改变行为的重构，`docs` 表示文档，`test` 表示测试，`build` 表示构建或依赖，`chore` 表示维护。
- 摘要使用祈使式、具体且简洁的中文描述；保留必要的命令、标识符、文件名和第三方名称。避免使用“更新一些内容”等无法说明结果的表述。
- 每个提交聚焦一个可独立评审的变更；提交正文仅在需要解释动机、兼容性或验证范围时添加，并继续使用中文。
- 分支使用 `feature/<简短英文主题>`、`fix/<简短英文主题>` 或 `docs/<简短英文主题>`；主题应对应单一工作项，不使用含糊的实验性名称承载正式实现。

## 面向人类的内容语言

- 所有面向人类的仓库内容和外部协作内容优先使用中文，包括 Issue、Pull Request、提交说明、README、功能文档、ADR、CLI 帮助与错误提示、发布说明和自动生成的报告。
- 使用 `$improve-codebase-architecture` 技能生成的 HTML 架构审查报告也必须使用中文；仅保留必要的代码标识符和既定 architecture 术语。
- 仅在中文会降低准确性或可读性时保留必要的英文技术术语、代码标识符、命令、文件名、协议字段和第三方产品名称；不得把完整的说明性内容默认写成英文。
- 修改既有面向人类的英文内容时，应在本次修改范围内同步转换为中文；上游原文、许可证或外部协议原样副本除外。
- 代码块中的可执行命令、环境变量、JSON 字段、退出码、标签值和配置键保持协议规定的原文；必要时在代码块外用中文解释。
- 文档审查应同时检查语言一致性和产品范围一致性，避免继续宣传已删除的命令或已废弃的架构术语。

## Agent 技能

### Issue tracker

Issue 和 PRD 存放在本仓库的 GitHub Issues 中，详见 `docs/agents/issue-tracker.md`。

### Triage labels

仓库使用默认的规范化 triage 标签，详见 `docs/agents/triage-labels.md`。

### Domain docs

本项目使用 GitHub Issue、README 和 `docs/adr/` 维护领域上下文，详见 `docs/agents/domain.md`。不要引用不存在的根级 `CONTEXT.md`。
