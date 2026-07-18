# git-sync

## 功能目标

将一个或多个 Git 工作区中的已跟踪变更、未跟踪文件和删除操作同步到远端对应的
项目目录，用于快速更新开发或测试环境。

## 使用场景

```text
okit git-sync run ./service-a ./service-b --host devbox --target-root /srv/src
okit git-sync run . --host devbox --target-root /srv/src --dry-run
```

## 行为规则

- 每个源路径必须是 Git 工作区；项目名取工作区根目录名称。
- 远端目标固定为 `<target-root>/<project-name>/`，`target-root` 是项目目录的父目录。
- 同步已修改、已新增、未跟踪和已删除路径；忽略未发生工作区变化的文件。
- `auto` 模式优先 rsync，不可用时回退 SFTP；显式模式失败时不自动切换。
- `--dry-run` 输出计划但不连接写入远端，也不更改配置。
- 多项目按输入顺序处理；单个项目失败不阻止后续项目，最终返回部分成功。
- 路径必须保持相对工作区结构，禁止通过 `..` 逃逸目标项目目录。

## 平台差异

Windows 和 Linux 都支持 SFTP。rsync 只在可执行文件存在且验证成功时启用。Windows
路径传入远端前统一转换为 `/` 分隔的相对路径。

## 错误与安全

- SSH 默认验证主机密钥，不采用自动信任未知主机策略。
- 认证优先使用 SSH agent 和用户已有密钥；不在配置或日志保存密码和私钥内容。
- 在真正同步前完成仓库、目标路径和连接参数校验。
- 删除操作必须限制在目标项目根目录内，并出现在 dry-run 计划中。

## 验收标准

- `GITSYNC-001`：目标路径符合 `target-root/project-name` 语义。
- `GITSYNC-002`：新增、修改、未跟踪和删除均能正确形成同步计划。
- `GITSYNC-003`：dry-run 不产生本地或远端持久化修改。
- `GITSYNC-004`：auto 模式按规则选择 rsync 或 SFTP。
- `GITSYNC-005`：路径遍历和未知主机密钥被拒绝。
- `GITSYNC-006`：多项目部分失败返回退出码 `3`。
