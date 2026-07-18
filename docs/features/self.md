# self

## 功能目标

为官方安装脚本安装的 `okit` 提供安全的版本检查、自升级和内置卸载能力，形成
安装、升级、卸载的完整生命周期。

## 使用场景

```text
okit self update --check
okit self update
okit self update --version v1.2.3 --dry-run
okit self uninstall
okit self uninstall --purge --yes
```

## 行为规则

### 自升级

- 默认检查并安装最新稳定版；`--prerelease` 才允许选择预发布版。
- `--version` 选择明确版本；只有显式指定较旧版本时才允许降级。
- 稳定最新版和显式版本通过固定名称 `release-manifest.json` 解析版本及当前 OS、架构
  的压缩包，不调用 GitHub REST API。只有未指定版本的 `--prerelease` 需要枚举
  Releases，并在存在 `GH_TOKEN` 或 `GITHUB_TOKEN` 时使用认证请求。
- 根据 manifest 下载 GitHub Release 压缩包及 `checksums.txt`。
- 下载内容先进入临时目录，通过 SHA-256 校验后才能替换当前程序。
- 使用安装锁阻止并发升级；替换失败时保留或恢复原版本。
- `--check` 只报告当前版和可用版本；`--dry-run` 展示完整计划，两者都不写文件。
- Windows 使用临时辅助进程，在当前进程退出后替换被占用的 EXE，并清理临时文件。

### 内置卸载

- 默认删除可执行文件、安装元数据和安装器添加的 PATH 项，保留用户的配置、缓存
  和备份。
- `--purge` 才删除整个 `OKIT_HOME`；删除前必须解析真实路径并确认目标严格位于
  预期用户目录，且需要交互确认或 `--yes`。
- 只撤销 `install.json` 记录的资源，不修改用户后来添加或其他程序管理的 PATH 项。
- Windows 使用临时辅助进程，在当前进程退出后完成 EXE 和自身临时文件删除。
- 已经不存在的托管资源按成功处理，使卸载步骤保持幂等。

## 安装方式边界

自管理仅适用于官方 `install.sh`、`install.ps1` 或手动标记为 `official` 的安装。
Scoop、WinGet、deb、rpm 等包管理器安装必须拒绝内置升级和卸载，并输出对应的包
管理器命令。缺失或损坏的 `install.json` 不得通过猜测路径执行替换或删除。

## 错误与安全

- 不自动请求管理员权限，不执行未经校验的下载内容。
- 更新服务器不可达、校验失败、磁盘不足或替换失败时，当前版本必须仍可运行。
- 日志不得记录令牌、代理认证信息或完整敏感 URL。
- purge、PATH 修改和可执行文件删除都必须支持 dry-run 并显示精确目标。

## 验收标准

- `SELF-001`：默认只选择高于当前版本的最新稳定版。
- `SELF-002`：预发布和降级必须显式请求。
- `SELF-003`：校验失败或下载中断不会替换当前可执行文件。
- `SELF-004`：替换失败能够恢复原版本。
- `SELF-005`：并发升级被安装锁阻止。
- `SELF-006`：Windows 辅助进程能够完成替换和卸载。
- `SELF-007`：默认卸载保留 `OKIT_HOME` 中的用户数据。
- `SELF-008`：purge 只能删除验证后的 `OKIT_HOME`。
- `SELF-009`：只移除安装元数据记录的 PATH 项和托管文件。
- `SELF-010`：包管理器安装被拒绝并得到正确提示。
- `SELF-011`：check 和 dry-run 不产生持久化副作用。
- `SELF-012`：稳定最新版和显式版本更新不依赖 GitHub REST API，并拒绝 schema、
  版本、目标或资产文件名不合法的 manifest。
