# info

## 功能目标

展示当前 `okit` 二进制、安装元数据、数据目录和 PATH 解析状态，帮助用户识别旧版本
或其他安装方式遮蔽当前程序的问题。命令只检查本机状态，不访问网络、不修改文件。

## 使用场景

```text
okit info
okit info --format json
okit --format json info
```

## 输出字段

- `version`、`commit`、`built`：当前二进制构建信息；
- `platform`：运行时操作系统和架构；
- `executable`、`install-dir`：当前进程对应的可执行文件和目录；
- `resolved`：当前 PATH 中执行 `okit` 时实际解析到的文件；
- `path-status`：`ok`、`missing` 或 `shadowed`；
- `install-dir-in-path`：当前进程 PATH 是否包含安装目录；
- `data-dir`、`config-file`、`metadata-file`：数据和配置位置；
- `metadata-status`：安装元数据为 `ok`、`missing` 或 `invalid`；
- `install-method`、`install-channel`、`install-version`：合法元数据中的安装信息；
- `warnings`：带稳定代码和可读消息的诊断列表。

文本模式将普通字段写 stdout、warning 写 stderr。JSON 模式输出单个对象并将 warning
包含在 `warnings` 数组中，不额外写 stderr。发现 warning 时命令仍返回 `0`；无法解析
当前可执行文件或数据目录等基础状态时返回 `1`。

## 安全边界

- 不检查远端更新；
- 不读取或输出配置内容；
- 不输出 Token、代理认证、完整环境变量或其他敏感信息；
- 不自动删除旧版本、调整 PATH 顺序或修复安装元数据。

## 验收标准

- `INFO-001`：输出构建、平台、可执行文件、数据及配置路径。
- `INFO-002`：PATH 首选文件与当前可执行文件不同时报告 `PATH_SHADOWED`。
- `INFO-003`：PATH 无法解析 `okit` 时报告 `PATH_MISSING`。
- `INFO-004`：安装元数据缺失或损坏时分别报告稳定状态和 warning，命令保持成功。
- `INFO-005`：合法元数据展示安装方式、通道和版本，但不输出配置内容。
- `INFO-006`：table 与 JSON 输出包含等价信息，JSON 可被标准解析器直接解析。
