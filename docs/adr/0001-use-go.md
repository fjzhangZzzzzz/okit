# ADR 0001：使用 Go 重新实现

- 状态：已接受
- 日期：2026-07-18

## 决策

使用 Go 重新实现 `okit`，交付单一跨平台可执行文件。Python 代码只作为功能和兼容
样本参考，不采用逐行迁移。

不重新实现动态自动注册、延迟加载、Rich 输出和性能监控框架。命令显式注册，输出
层只承担颜色、表格、JSON 和错误格式化。

## 原因

Go 更适合无运行时依赖的 CLI 分发、Linux/Windows 交叉构建和 GoReleaser 发布。
删除低价值框架可以降低启动、维护和测试成本。

## 影响

- CLI 和配置兼容性以新文档为准，而不是保持 Python 内部结构。
- 平台相关功能使用 build tags 隔离。
- 重实现必须遵循文档先行和 TDD。

## 目标结构

```text
okit/
├── cmd/okit/main.go
├── internal/
│   ├── cli/
│   ├── hex/
│   ├── peinspect/
│   ├── gitsync/
│   ├── shell/
│   ├── mobaxterm/
│   │   ├── theme/
│   │   └── license/
│   ├── selfmanage/
│   ├── config/
│   └── releaseassets/（发布契约测试）
├── scripts/
│   ├── install.sh
│   └── install.ps1
├── .github/workflows/
├── .goreleaser.yaml
└── go.mod
```

测试文件与实现放在同一包中。除非以后明确提供公共 Go API，否则不建立 `pkg/`。
外部进程、文件系统、SSH 和注册表接口由使用方包定义，避免形成通用 `utils` 包。
