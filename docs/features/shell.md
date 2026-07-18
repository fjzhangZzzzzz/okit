# shell

## 功能目标

在多台机器间同步 Shell 配置，并以可恢复的方式在用户启动文件中启用或禁用配置。

## 使用场景

```text
okit shell sync bash
okit shell enable powershell --dry-run
okit shell status zsh
```

## 行为规则

- 支持 `bash`、`zsh`、`powershell` 和 `cmd`；不支持的平台组合返回使用错误。
- `sync` 从已配置的 Git 仓库更新 okit 管理的配置副本，不直接覆盖用户启动文件。
- 配置仓库根目录分别使用 `bash`、`zsh`、`powershell`、`cmd` 四个文件名；只需
  提供实际使用的平台文件。
- `source` 只输出当前 Shell 应使用的加载命令。
- `enable` 向启动文件写入带稳定起止标记的托管区块，并在修改前创建备份。
- `disable` 只删除 okit 托管区块，不改变用户其他内容。
- `enable`、`disable` 必须幂等；重复执行不得产生重复区块或无意义备份。
- `status` 报告配置副本、启动文件、托管区块和仓库状态。
- 文件更新采用同目录临时文件和原子替换；失败时保留原文件。

## 平台差异

- Bash/Zsh 使用对应 rc 文件；PowerShell 通过平台 API/进程边界解析 `$PROFILE`。
- CMD 使用独立、明确记录的加载机制，不假设存在 Unix rc 文件。
- Git Bash 路径转换必须经过专门测试，不在 source 行中写入不可解析的 Windows 路径。

## 错误与安全

默认不跟随指向 okit 管理目录之外的危险符号链接。所有计划写入应支持 `--dry-run`；
格式异常的既有托管区块必须拒绝修改并提示人工处理。

## 验收标准

- `SHELL-001`：enable/disable 对支持的 Shell 均保持幂等。
- `SHELL-002`：修改失败后原启动文件内容不变。
- `SHELL-003`：只修改带 okit 标记的托管区块。
- `SHELL-004`：dry-run 不创建备份、目录或文件。
- `SHELL-005`：Git Bash 和 PowerShell 路径可被各自 Shell 正确解析。
- `SHELL-006`：测试只使用临时 OKIT_HOME 和临时用户目录。
