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

`info`、`hex`、`pe`、`git-sync`、`shell`、`config` 和 `self` 均不再受支持，且没有兼容别名。
