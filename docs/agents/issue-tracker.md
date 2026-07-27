# Issue tracker：GitHub

本仓库的 Issue 和 PRD 存放在 GitHub Issues 中。所有 Issue 操作使用 `gh` CLI。

## 常用操作

- 创建 Issue：`gh issue create --title "..." --body "..."`。
- 阅读 Issue：`gh issue view <number> --comments`。
- 列出 Issue：`gh issue list`，并按需要使用状态和标签过滤。
- 评论 Issue：`gh issue comment <number> --body "..."`。
- 添加或移除标签：`gh issue edit <number> --add-label "..."` / `gh issue edit <number> --remove-label "..."`。
- 关闭 Issue：`gh issue close <number> --comment "..."`。

仓库地址从 Git remote 推断为 `fjzhangZzzzzz/okit`。

## Pull Request 定位

Pull Request 不是需求收集入口；实现请求应先记录在 Issue 中。

## 技能需要发布到 Issue tracker 时

创建 GitHub Issue。

## 技能需要获取相关工单时

运行 `gh issue view <number> --comments`。
