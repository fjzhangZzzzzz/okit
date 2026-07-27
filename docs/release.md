# 发布规范

Go 版本使用 GitHub Actions 和 GoReleaser 发布。GoReleaser 只消费已存在的 Git
tag，不负责决定或创建版本号。

## 版本与触发

- 遵循语义化版本，tag 格式为 `vMAJOR.MINOR.PATCH`。
- 预发布使用 `vMAJOR.MINOR.PATCH-rc.N`。
- tag 必须指向已通过 Linux/Windows CI 的提交。
- 正式发布使用 GitHub Release，不再发布到 PyPI。

## 发布产物

最低目标矩阵：

| 系统 | 架构 | 格式 |
| --- | --- | --- |
| Linux | amd64、arm64 | `.tar.gz` |
| Windows | amd64、arm64 | `.zip` |

每次 Release 必须包含以下独立资产：

- 各目标平台的版本化压缩包；
- `checksums.txt`；
- `release-manifest.json`；
- `install.sh`；
- `install.ps1`。

安装脚本是正式发布产物，而不只是仓库中的开发辅助脚本。GoReleaser 发布流程从
`scripts/` 取得脚本并以固定资产名上传，使 `releases/latest/download/` 地址长期
稳定。发布同时生成变更说明并包含许可证文件。二进制通过构建参数注入版本、提交号
和构建时间，`okit --version` 必须能够显示这些信息。

`release-manifest.json` 使用固定资产名，记录 tag、校验和文件名以及各系统架构对应的
版本化压缩包。最新版通过 `releases/latest/download/release-manifest.json` 获取，
固定版本通过 `releases/download/<tag>/release-manifest.json` 获取。公开安装流程不得
调用 GitHub REST Releases API，避免共享出口 IP 的未认证限流。

安装脚本必须写入 `$OKIT_HOME/install.json`（默认 `~/.okit/install.json`），记录
版本、安装方式、可执行文件路径、
发布通道以及由安装器添加的 PATH 项。`okit upgrade` 使用同一组压缩包和
`checksums.txt`，不维护第二套更新产物。

## 自动流程

1. 检出完整 Git 历史和 tag；
2. 运行格式化检查、静态检查和 `go test ./...`；
3. 根据 tag 生成并校验 `release-manifest.json`；
4. 使用 GoReleaser 构建、归档并生成校验和；
5. 创建 GitHub Release，上传压缩包、manifest、校验和及两个安装脚本；
6. 在干净的 Linux/Windows 环境执行安装冒烟测试；
7. 从上一稳定版执行 `okit upgrade`，并验证内置卸载；
8. 冒烟测试失败时将发布标记为失败，不更新安装入口。

工作流调用仓库中的 `scripts/smoke-release-lifecycle.sh` 和
`scripts/smoke-release-lifecycle.ps1`，避免 Linux 与 Windows 的生命周期校验逻辑只存在于工作流内。
它们复用 `smoke-runtime-*` 脚本验证最终安装产物；普通 CI 也使用相同脚本验证源码构建产物。
冒烟失败必须显示测试阶段、二进制路径、期望版本和 `okit --version` 的实际输出。

运行时冒烟不执行安装、升级或卸载，可直接验证本地构建：

```sh
go build -o ./okit-runtime ./cmd/okit
sh scripts/smoke-runtime-linux.sh --executable ./okit-runtime --version dev
```

```powershell
go build -o ./okit-runtime.exe ./cmd/okit
scripts/smoke-runtime-windows.ps1 -Executable ./okit-runtime.exe -Version dev
bash scripts/smoke-runtime-windows-git-bash.sh --executable ./okit-runtime.exe --version dev
```

## 本地冒烟测试

发布前可对本地构建执行版本、帮助、核心命令及卸载生命周期检查。测试使用临时目录，
不会修改用户现有的 `OKIT_HOME` 或安装目录：

Linux：

```sh
go build -ldflags "-X main.version=v2.0.0" -o ./okit-smoke ./cmd/okit
sh scripts/smoke-release-lifecycle.sh --binary ./okit-smoke --version v2.0.0
```

Windows PowerShell：

```powershell
go build -ldflags "-X main.version=v2.0.0" -o ./okit-smoke.exe ./cmd/okit
scripts/smoke-release-lifecycle.ps1 -Mode binary -Binary ./okit-smoke.exe -Version v2.0.0
```

对已经发布的版本运行完整下载安装和跨版本升级检查：

```sh
sh scripts/smoke-release-lifecycle.sh --release --version v2.0.0
```

```powershell
scripts/smoke-release-lifecycle.ps1 -Mode release -Version v2.0.0
```

release 模式需要 GitHub CLI 和网络访问；binary 模式不验证 GitHub Release 上传环节。

## 安装入口

产品对外提供以下稳定命令：

Linux：

```sh
curl -fsSL https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.sh | OKIT_VERSION=v1.2.3 sh
```

Windows PowerShell：

```powershell
$env:OKIT_VERSION = 'v1.2.3'
irm https://github.com/fjzhangZzzzzz/okit/releases/latest/download/install.ps1 | iex
```

- `install.sh` 下载匹配 Linux 架构的压缩包，验证校验和后安装。
- `install.ps1` 完成等价的 Windows 下载、校验和安装流程。
- 安装器通过固定名称 manifest 解析最新版，不依赖 GitHub REST API 或用户 Token。
- 安装脚本默认安装到用户可写目录，不隐式请求管理员权限。
- 安装脚本必须支持固定版本；`latest` 只能解析最新正式版本，不选择预发布。
- 固定版本通过安装器参数选择：Linux 使用 `--version vMAJOR.MINOR.PATCH`，
  PowerShell 使用 `-Version vMAJOR.MINOR.PATCH`。
- 包含预发布标识的版本写入 `channel: prerelease`；正式版本写入
  `channel: stable`。
- 脚本不得要求系统预装 Go、Python、uv 或 GoReleaser。
- 安装目录不在 PATH 时，脚本只添加自身的用户级目录或给出明确提示，不覆盖既有
  PATH 内容。

安装、升级和卸载应保持幂等，不修改与 `okit` 无关的 PATH 条目或文件。未来可在
GitHub Release 稳定后增加 Scoop、WinGet、deb 或 rpm，但不作为首个版本的阻塞项。
通过包管理器安装时，`okit` 不接管升级或卸载，必须提示用户使用原包管理器。

## 预发布与清理

- `vMAJOR.MINOR.PATCH-rc.N` 发布为 GitHub Pre-release，用于真实安装和升级验收。
- `okit upgrade --prerelease` 允许选择预发布版本；精确升级使用
  `okit upgrade --version vMAJOR.MINOR.PATCH-rc.N`。
- 对应正式版本 `vMAJOR.MINOR.PATCH` 发布并完成 Linux/Windows 生命周期烟测后，
  工作流立即删除所有 `vMAJOR.MINOR.PATCH-rc.N` GitHub Release 及其 tag。

## 发布前检查

- tag 与 `okit --version` 一致；
- 所有目标压缩包均包含单个可执行文件、README 和 LICENSE；
- 校验和可验证；
- Release 中存在固定名称的 `install.sh` 和 `install.ps1`；
- Release 中存在合法的 `release-manifest.json`，且列出的资产全部存在；
- README 中的一键安装命令能够从 Release 资产完成全新安装和升级；
- 安装脚本拒绝校验和不匹配的压缩包；
- 从上一稳定版自升级成功，损坏产物和中断场景能够回滚；
- 默认卸载保留用户数据，`--purge` 仅删除经过验证的 `OKIT_HOME`；
- `--help`、`upgrade --help`、`uninstall --help` 的只读冒烟测试通过；
- MobaXterm 命令只包含在 Windows 可执行文件的可用路径中。
