# okit

`okit` 是个人使用的 MobaXterm 维护与自身安装生命周期命令行工具，使用 Go 实现并提供 Linux/Windows 发布产物。

## 命令

```text
okit mobaxterm status
okit mobaxterm theme <list|apply|restore|cache>
okit mobaxterm license <generate|deploy|inspect|verify>
okit upgrade [--check] [--version VERSION] [--prerelease] [--dry-run]
okit uninstall [--purge] [--yes] [--dry-run]
```

`upgrade` 只适用于已发布版本。`uninstall --purge` 会删除用户数据，因此需要明确确认；`--dry-run` 始终不修改文件。

## 安装

Linux：

```sh
curl -fsSL https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.sh | sh
```

Windows PowerShell：

```powershell
irm https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.ps1 | iex
```

安装后可使用 `okit upgrade --version v1.2.3` 升级指定版本，或使用 `okit upgrade --prerelease` 选择预发布版本。

## 文档

- [CLI 规范](docs/cli.md)
- [MobaXterm 功能说明](docs/features/mobaxterm.md)
- [测试说明](docs/testing.md)
- [发布说明](docs/release.md)
