# okit

自用 Python 工具集，作为 UV Tool 扩展分发。

规范：
- 按照类型划分工具目录，每个工具的名称是唯一标识符

## 工具列表

okit 包含以下工具：

| 命令名称 | 用途说明 | 分类 | 文档链接 |
|---------|---------|------|---------|
| `gitdiffsync` | Git 项目同步工具，支持 rsync/SFTP 同步变更文件到远程服务器 | 🔧 开发工具 | - |
| `clonerepos` | 批量克隆 Git 仓库工具 | 🔧 开发工具 | - |
| `pedump` | PE 文件（EXE/DLL）头信息和节信息解析工具 | 🔧 开发工具 | - |
| `mobaxterm-pro` | MobaXterm Professional 许可证管理工具<br/>• 自动探测系统中安装的 MobaXterm 信息<br/>• 生成 Custom.mxtpro 许可证文件<br/>• 一键部署许可证文件到安装目录 | 🔐 安全工具 | [使用文档](docs/mobaxterm_pro_usage.md) |
| `shellconfig` | Shell 配置管理工具<br/>• 同步 Shell 配置文件<br/>• 管理配置状态<br/>• 备份和恢复配置 | ⚙️ 配置工具 | - |
| `minimal` | 最小化示例工具，展示工具开发模式 | 📚 示例工具 | - |

## 快速开始

### 安装

```bash
uv tool install okit
```

### 使用

```bash
# 查看帮助
okit --help

# 查看具体命令帮助
okit COMMAND --help

# 打开补全（支持 bash/zsh/fish）
okit completion enable

# 关闭补全
okit completion disable
```

## 开发

详细的开发指导请参考 [开发指导文档](docs/development_guide.md)，包括：

- 架构设计和自动注册机制
- 工具脚本开发模式
- 配置和数据管理
- 开发环境搭建
- 发布流程
- 最佳实践

### 快速开发

```bash
git clone https://github.com/fjzhangZzzzzz/okit.git
cd okit

# 本地安装开发版本
uv tool install -e . --reinstall
```

## 版本号规约

采用语义化版本，符合 PEP 440，遵循格式 `[主版本号]!.[次版本号].[修订号][扩展标识符]`

- 主版本号（Major）：重大变更（如 API 不兼容更新）
- 次版本号（Minor）：向后兼容的功能性更新
- 修订号（Micro）：向后兼容的 Bug 修复或小改动

扩展标识符包括：开发版（dev）、Alpha 预发布（a）、Beta 预发布（b）、RC 预发布（rc）、正式版、后发布版（post）。

## 自动化发布

项目使用 GitHub Actions 实现自动化发布流程：

1. 开发分支自动发布到 TestPyPI
2. 正式 tag 自动发布到 PyPI
3. 版本号自动同步和管理

详细流程请参考 [开发指导文档](docs/development_guide.md)。