# ADR 0003：配置与数据目录

- 状态：已接受
- 日期：2026-07-18

## 决策

使用 `OKIT_HOME` 作为统一数据根目录，默认值为 `~/.okit`：

```text
~/.okit/
├── config.yaml
├── install.json
├── data/
│   ├── git-sync/
│   ├── shell/
│   └── mobaxterm/
├── cache/
└── backups/
```

配置键使用点分层级。敏感信息不写入 `config.yaml`；SSH 凭据交由系统 SSH agent、
密钥文件权限和平台凭据设施管理。

`install.json` 由官方安装器维护，至少包含安装方式、版本、发布通道、可执行文件路径
以及由安装器添加的 PATH 项。业务配置命令不得修改该文件；自升级和卸载通过它判断
自己能够安全管理的资源。

## 原因

沿用 `~/.okit` 可以降低 Python 到 Go 的迁移成本，`OKIT_HOME` 让测试和便携环境
能够完整隔离。统一根目录也便于备份与卸载。

## 影响

- 测试必须设置临时 `OKIT_HOME`。
- 删除和清理操作必须先验证目标位于解析后的 `OKIT_HOME` 内。
- 若未来迁移到 XDG/Windows 标准目录，需要新增 ADR 和显式迁移流程。
