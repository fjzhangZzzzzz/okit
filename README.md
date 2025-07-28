# okit

自用 Python 工具集，作为 UV Tool 扩展分发。

规范：
- 按照类型划分工具目录，每个工具的名称是唯一标识符


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

### 搭建环境

```bash
git clone https://github.com/fjzhangZzzzzz/okit.git
cd okit

# 修改代码

# 本地构建 okit
uv build .

# 本地安装 okit
uv tool install -e . --reinstall

# 发布到 TestPyPI
uv publish --index testpypi --token YOUR_TEST_TOKEN

# 发布到 PyPI
uv publish --token YOUR_PYPI_TOKEN

# 从 TestPyPI 安装（需指定索引）
uv tool install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple okit==1.0.1b6

# 从正式 PyPI 安装
uv tool install okit
```

### 架构设计

源码目录结构
```
okit/
  ├── cli/           # 命令行入口
  ├── core/          # 核心框架
  ├── tools/         # 工具脚本
  ├── utils/         # 通用工具函数
  └── __init__.py
```

命令行入口会自动扫描 `tools/` 目录下的脚本，自动导入并注册 CLI 命令。

#### 工具脚本开发

工具脚本使用 `BaseTool` 基类和 `@okit_tool` 装饰器开发：

```python
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool

@okit_tool("toolname", "Tool description")
class MyTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        # 添加 CLI 命令
        pass
```

详细开发指南请参考 `src/okit/tools/minimal_example.py` 示例。

#### 日志输出

```python
from okit.utils.log import logger, console

def some_func():
    # 普通日志输出
    logger.info("开始同步")
    logger.error("同步失败")

    # 富文本输出
    console.print("[green]同步成功[/green]")
    console.print("[bold red]严重错误[/bold red]")
```

### 版本号规约

#### 版本号核心
采用语义化版本，符合 PEP 440，遵循格式 `[主版本号]!.[次版本号].[修订号][扩展标识符]`
- 主版本号（Major）：重大变更（如 API 不兼容更新），递增时重置次版本和修订号。
- 次版本号（Minor）：向后兼容的功能性更新，递增时重置修订号。
- 修订号（Micro）：向后兼容的 Bug 修复或小改动。

#### 扩展标识符（可选）
- 开发版，格式示例 `1.0.0.dev1`
- Alpha 预发布，格式示例 `1.0.0a1`，内部测试
- Beta 预发布，格式示例 `1.0.0b2`，公开测试
- RC 预发布，格式示例 `1.0.0rc3`，候选发布
- 正式版，格式示例 `1.0.0`，正式发布，稳定可用
- 后发布版，格式示例 `1.0.0.post1`，修正补丁

### 自动化发布流程

推荐的分支与发布流程如下：

1. **开发分支**：从 main 分支拉出开发分支（如 v1.1.0-dev），在该分支上进行开发和测试。
2. **测试发布**：在开发分支上，手动触发 workflow，每次会自动生成开发版本号（如 v1.1.0-devN，N 为 github workflow 构建号），写入 `src/okit/__init__.py`，并发布到 TestPyPI。此过程不会 commit 版本号变更。
3. **预发布分支（可选）**，开发验证通过后可基于开发分支拉出预发布分支（如 v1.1.0-alpha），具体需要几轮预发布视功能复杂度和测试周期决定，该阶段的发布与测试发布一致，自动生成的版本号对应关系为：
   1. Alpha 预发布分支名 `v1.1.0-alpha`，对应预发布版本号 `v1.1.0aN`
   2. Beta 预发布分支名 `v1.1.0-beta`，对应预发布版本号 `v1.1.0bN`
4. **功能测试**：通过 pip 指定 testpypi 索引安装测试包，进行功能验证。
5. **正式发布**：测试通过后，将开发分支合并回 main 分支，并在 main 分支最新 commit 上打正式 tag（如 v1.1.0）。workflow 会自动检查并同步 `src/okit/__init__.py` 版本号为 tag，若不一致则自动 commit 并 push，然后发布到 PyPI。
6. **注意事项**：
   - 发布内容为 tag 或触发分支指向的 commit 代码。
   - 开发分支发布会自动发布到 TestPyPI，正式 tag 自动发布到 PyPI。
   - 请始终在 main 分支最新 commit 上打正式 tag，确保发布内容为最新。
   - 不允许在 main 分支上手动触发 workflow，即使这样操作也会使 workflow 失败。

**自动化发布无需手动操作，只需管理好分支与 tag，GitHub Actions 会自动完成发布。**