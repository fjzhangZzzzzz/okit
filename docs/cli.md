# CLI 规范

`okit` 仅提供 MobaXterm 维护与自身安装生命周期操作：

```text
okit mobaxterm status
okit mobaxterm theme <list|apply|restore|cache>
okit mobaxterm license <generate|deploy|inspect|verify>
okit upgrade [--check] [--version VERSION] [--prerelease] [--dry-run]
okit uninstall [--purge] [--yes] [--dry-run]
```

所有命令均支持 `--help`。`upgrade` 在开发构建中会明确提示只能由已发布版本执行。
`uninstall --purge` 默认要求交互确认；`--dry-run` 不会修改文件。

## 升级结果

`okit upgrade --format json` 输出版本化的升级结果，而不是由多个布尔字段拼接状态：

```json
{
  "schema_version": 1,
  "mode": "check",
  "status": "available",
  "current": "v1.2.3",
  "target": "v1.3.0",
  "next_action": {
    "kind": "run_upgrade",
    "command": ["okit", "upgrade"]
  }
}
```

`mode` 为 `check`、`dry_run` 或 `apply`；`status` 为 `up_to_date`、`available`、`planned`、`applied`、`scheduled`、`unsupported` 或 `invalid_installation`。交互进度仅写入 stderr，不属于最终 JSON 结果。

`info`、`hex`、`pe`、`git-sync`、`shell`、`config` 和 `self` 均不再受支持，且没有兼容别名。
