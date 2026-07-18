# okit

`okit` 是面向开发与日常运维场景的跨平台命令行工具集。项目使用 Go 实现，
提供单一可执行文件、清晰一致的命令界面，以及可验证的
Linux/Windows 发布产物。

## 功能范围

当前功能：

| 命令 | 用途 | 平台 |
| --- | --- | --- |
| `okit hex` | 以十六进制、八进制、字符等格式查看文件 | Linux / Windows |
| `okit pe` | 查看 PE 可执行文件的头部和节信息 | Linux / Windows |
| `okit git-sync` | 将 Git 工作区中的变更文件同步到远端 | Linux / Windows |
| `okit shell` | 同步、启用和管理 Shell 配置 | Linux / Windows |
| `okit mobaxterm` | 管理 MobaXterm 检测、主题和许可证 | Windows |
| `okit self` | 检查更新、自升级和内置卸载 | Linux / Windows |

产品不包含 `clonerepos`、`minimal`、动态命令注册、延迟加载及性能监控框架。
输出层只提供必要的颜色、表格、JSON 和错误格式化能力。

## 命令概览

```text
okit hex <file...>
okit pe inspect <file...>
okit git-sync run <path...>
okit shell <sync|source|enable|disable|status> <shell>
okit mobaxterm status
okit mobaxterm theme <list|apply|restore|cache>
okit mobaxterm license <generate|deploy|inspect|verify>
okit self update [--check]
okit self uninstall [--purge]
```

完整命令和行为约定参见 [CLI 规范](docs/cli.md)。

## 安装与状态

产品提供以下稳定的一键安装入口。

Linux：

```sh
curl -fsSL https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.sh | sh
```

Windows PowerShell：

```powershell
irm https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.ps1 | iex
```

`install.sh` 和 `install.ps1` 是每次 GitHub Release 的独立发布产物，不要求用户
预先安装 Go、Python 或 uv。安装脚本负责识别平台和架构、下载对应压缩包、验证
SHA-256 校验和并安装到用户目录。

发布流程参见 [发布规范](docs/release.md)。

## 文档

- [CLI 规范](docs/cli.md)
- [测试与 TDD](docs/testing.md)
- [发布规范](docs/release.md)
- 功能规范：[hex](docs/features/hex.md)、[pe](docs/features/pe.md)、
  [git-sync](docs/features/git-sync.md)、[shell](docs/features/shell.md)、
  [mobaxterm](docs/features/mobaxterm.md)、[self](docs/features/self.md)
- 架构决策：[ADR](docs/adr/)

## 开发原则

1. 文档先行：行为变化先更新 CLI 或功能规范。
2. 测试驱动：先提交失败测试，再完成最小实现并重构。
3. 平台明确：平台相关逻辑使用 Go build tags 隔离。
4. 安全默认：文件写入提供备份，高风险操作支持 `--dry-run` 或显式确认。
5. 保持边界：除非需要公开 Go API，否则业务代码只放在 `internal/`。

## 许可证

项目采用 [MIT License](LICENSE)。MobaXterm 许可证功能仅应在用户拥有合法授权的
范围内使用。
