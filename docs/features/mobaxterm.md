# mobaxterm

## 功能目标

在 Windows 上统一提供 MobaXterm 安装检测、主题管理和已授权许可证文件管理。

## 使用场景

```text
okit mobaxterm status
okit mobaxterm theme list --search solarized
okit mobaxterm theme apply SolarizedDark --dry-run
okit mobaxterm license deploy --username user --dry-run
```

## 行为规则

### 安装检测

- 按明确优先级检查注册表、包管理器、常见安装路径、PATH 和用户指定路径。
- 返回安装路径、可执行文件、版本、检测来源、配置路径和许可证文件状态。
- 多个安装并存时报告全部候选，并明确默认目标。

### 主题

- 从本地缓存列出和搜索主题；缓存来源默认为 iTerm2-Color-Schemes 仓库。
- 应用主题前备份 `MobaXterm.ini`，除非显式指定 `--no-backup`。
- 只修改已知颜色键，保留其他配置、注释和换行风格。
- restore 默认选择最近有效备份，也可指定备份文件。
- cache update 更新或创建缓存；clean 仅删除 okit 管理的缓存目录。

### 许可证

- generate 根据用户名和版本生成 `Custom.mxtpro` 到指定位置。
- deploy 自动检测目标安装和版本，写入前显示计划并处理权限错误。
- inspect 读取许可证文件或 key 并输出可解析信息。
- verify 校验用户名、版本和许可证数据是否一致。
- 许可证算法的兼容样本应固定在测试数据中，防止重实现产生不兼容文件。

## 平台差异

该功能仅支持 Windows。非 Windows 平台返回退出码 `2`，不得创建缓存或配置。

## 错误与安全

- 注册表和版本探测不启动不受信任的可执行文件；必须执行时通过受控进程接口和超时。
- apply、restore、deploy 支持 dry-run；写入前备份并使用原子替换。
- 不覆盖无法解析的配置或许可证文件。
- 许可证相关能力仅限合法授权范围，文档和输出不得暗示绕过商业授权。

## 验收标准

- `MOBA-001`：各检测来源按固定优先级合并并去重。
- `MOBA-002`：主题应用只改变受支持颜色键并保留其他内容。
- `MOBA-003`：主题写入失败时可从备份恢复。
- `MOBA-004`：缓存 clean 不删除 okit 管理目录之外的文件。
- `MOBA-005`：许可证生成、解析和校验通过固定兼容样本。
- `MOBA-006`：deploy dry-run 不写入安装目录。
- `MOBA-007`：非 Windows 平台不产生任何副作用。
