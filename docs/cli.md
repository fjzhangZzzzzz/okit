# CLI 规范

本文档定义 Go 版本 `okit` 的稳定命令契约。功能细节和验收条件由
[`features/`](features/) 下的文档补充。

## 通用约定

- 命令采用“名词功能 + 动词动作”的结构，名称使用小写 kebab-case。
- 帮助和正常结果写入 stdout；诊断、警告和错误写入 stderr。
- 成功返回 `0`；使用错误返回 `2`；运行失败返回 `1`；部分成功返回 `3`。
- `--format table|json|jsonl|csv|raw` 只作用于明确声明支持格式选择的命令；帮助只
  展示当前叶命令实际支持的格式。不支持的组合返回使用错误。
- 颜色只能作为非语义增强，任何输出都不得依赖颜色才能理解；`--no-color` 和
  `NO_COLOR` 保证关闭颜色。
- `--quiet` 保留业务结果、错误和重要安全警告，但隐藏进度、装饰信息和非必要诊断；
  `--verbose` 输出额外诊断信息，两者互斥。
- 成功的查询命令必须输出结果或明确的空状态；修改命令必须说明已修改、未变化、
  已取消或已调度。dry-run 必须明确说明没有产生变更。
- 会修改文件或远端状态的命令应先校验全部输入；支持 `--dry-run` 的命令不得在
  dry-run 模式产生持久化变更。
- `--force` 只跳过交互确认，不跳过参数、安全或权限校验。

## 帮助契约

- 根命令和命令树中的每一级命令均支持 `-h`、`--help`；帮助写入 stdout、返回 `0`，
  且不得执行对应业务操作。
- `okit help <command...>` 等价于目标命令的 `--help`，例如
  `okit help mobaxterm theme apply`。
- 上下文帮助至少包含完整调用路径、位置参数、当前命令参数和继承的全局参数。
- 未知命令、未知参数及参数数量错误写入 stderr 并返回 `2`，默认不附带整段 usage。

验收条件：

- `CLI-001`：所有已记录的命令层级均能输出自身上下文帮助，且不执行功能逻辑。
- `CLI-002`：`help` 命令能够定位任意已记录的嵌套命令。
- `CLI-003`：未知参数、缺少参数和多余参数统一作为使用错误返回 `2`。

全局参数：

```text
--format table|json|jsonl|csv|raw
--no-color
--quiet
--verbose
--version
--help
```

## 命令树

```text
okit
├── info
├── hex <file...>
├── pe
│   └── inspect <file...>
├── git-sync
│   ├── run <path...>
│   ├── status
│   └── config <get|set|list>
├── shell
│   ├── sync <shell>
│   ├── source <shell>
│   ├── enable <shell>
│   ├── disable <shell>
│   ├── status <shell>
│   └── config <get|set|list>
├── mobaxterm
│   ├── status
│   ├── theme
│   │   ├── list
│   │   ├── apply <name>
│   │   ├── restore
│   │   └── cache <update|clean|status>
│   └── license
│       ├── generate
│       ├── deploy
│       ├── inspect
│       └── verify
└── self
    ├── update
    └── uninstall
```

## 命令参数

### `okit info`

```text
okit info [--format table|json]
```

支持 `table|json`。仅采集本地构建、路径和安装状态，不检查网络更新。完整语义参见
[`features/info.md`](features/info.md)。

### `okit hex`

```text
okit hex <file...> [--display canonical|hex|octal|char|decimal]
                     [--word-size 1|2] [--skip N] [--length N]
                     [--no-squeeze]
```

默认为 `canonical`。`--skip` 和 `--length` 使用字节数，必须为非负整数。
支持 `table|raw`；两者都输出可直接消费的 hexdump，多文件输入包含文件边界。

### `okit pe inspect`

```text
okit pe inspect <file...> [--format table|json|csv]
```

### `okit git-sync`

```text
okit git-sync run <path...> --host HOST --target-root PATH
    [--user USER] [--port PORT] [--transport auto|rsync|sftp]
    [--dry-run]
okit git-sync status
okit git-sync config get <key>
okit git-sync config set <key> <value>
okit git-sync config list
```

`run` 支持 `table|json|jsonl`；`status` 和配置命令支持 `table|json`，配置 `get`
额外支持 `raw`。

完整同步语义参见 [`features/git-sync.md`](features/git-sync.md)。

### `okit shell`

```text
okit shell sync <bash|zsh|powershell|cmd> [--dry-run]
okit shell source <bash|zsh|powershell|cmd>
okit shell enable <bash|zsh|powershell|cmd> [--dry-run] [--force]
okit shell disable <bash|zsh|powershell|cmd> [--dry-run] [--force]
okit shell status <bash|zsh|powershell|cmd>
okit shell config get <key>
okit shell config set <key> <value>
okit shell config list
```

查询、修改和配置命令支持 `table|json`；`source` 支持 `table|raw` 并保持输出为可直接
执行的 shell 片段；配置 `get` 额外支持 `raw`。

### `okit mobaxterm`

```text
okit mobaxterm status
okit mobaxterm theme list [--search TEXT] [--limit N]
okit mobaxterm theme apply <name> [--no-backup] [--force] [--dry-run]
okit mobaxterm theme restore [--backup FILE] [--force] [--dry-run]
okit mobaxterm theme cache update|clean|status
okit mobaxterm license generate --username NAME --version VERSION --output FILE
okit mobaxterm license deploy --username NAME [--version VERSION] [--force] [--dry-run]
okit mobaxterm license inspect <file-or-key>
okit mobaxterm license verify <file-or-key> --username NAME --version VERSION
```

MobaXterm 的查询、缓存、主题和许可证叶命令支持 `table|json`。

完整行为参见 [`features/mobaxterm.md`](features/mobaxterm.md)。

### `okit self`

```text
okit self update [--check] [--version VERSION] [--prerelease] [--dry-run]
okit self uninstall [--purge] [--yes] [--dry-run]
```

`--check` 只检查是否存在更新；`--version` 接受带 `v` 的语义化版本。完整生命周期
行为参见 [`features/self.md`](features/self.md)。更新和卸载支持 `table|json`。

## 配置与环境

- `OKIT_HOME`：覆盖数据根目录，默认 `~/.okit`。Windows Git Bash 可使用
  `C:/Users/name/.okit` 或 `/c/Users/name/.okit`；无法映射到盘符的 POSIX 路径会被拒绝。
- `NO_COLOR`：存在且非空时禁用颜色。
- 配置键使用点分层级，例如 `git-sync.host`。
- 密码、私钥内容和访问令牌不得写入普通配置文件或日志。

## 兼容性

Go 版本不保证兼容旧 Python 命令名称。首次稳定版本发布后，已有命令和退出码按
语义化版本管理；破坏性变更必须提升主版本并更新本规范。
