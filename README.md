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

# 构建 okit
uv build .

# 安装 okit
uv tool install -e .

# 发布到 TestPyPI
uv publish --index testpypi --token YOUR_TEST_TOKEN

# 发布到 PyPI
uv publish --token YOUR_PYPI_TOKEN

# 从 TestPyPI 安装（需指定索引）
uv pip install -i https://test.pypi.org/simple/ okit

# 从正式 PyPI 安装
uv pip install okit
```

### 架构设计

源码目录结构
```
okit/
  ├── cli/           # 命令行入口
  ├── utils/         # 通用工具函数
  ├── data/          # 数据处理相关工具
  ├── net/           # 网络相关工具
  ├── image/         # 图像处理相关工具
  └── __init__.py
```

命令行入口中会自动扫描已知工具分类目录下脚本，自动导入并注册 cli 命令。

对于工具脚本，示例如下：
```python
# okit/net/http_client.py
import click

@click.command()
def cli():
    """HTTP 客户端工具"""
    click.echo("Hello from http_client!")
```

关于工具脚本的日志输出：
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

### 自动化发布流程

推荐的分支与发布流程如下：

1. **开发分支**：从 main 分支拉出开发分支（如 v1.1.0-dev），在该分支上进行开发和测试。
2. **测试发布**：在开发分支上，手动触发 workflow，每次会自动生成 `分支-日期-序号` 格式的英文版本号（如 v1.1.0-dev-20250710-1），写入 `src/okit/__init__.py`，并发布到 TestPyPI。此过程不会 commit 版本号变更。
3. **功能测试**：通过 pip 指定 testpypi 索引安装测试包，进行功能验证。
4. **正式发布**：测试通过后，将开发分支合并回 main 分支，并在 main 分支最新 commit 上打正式 tag（如 v1.1.0）。workflow 会自动检查并同步 `src/okit/__init__.py` 版本号为 tag，若不一致则自动 commit 并 push，然后发布到 PyPI。
5. **注意事项**：
   - 发布内容为 tag 或触发分支指向的 commit 代码。
   - 测试 tag（包含 dev/alpha/beta/rc）或开发分支发布会自动发布到 TestPyPI，正式 tag 自动发布到 PyPI。
   - 请始终在 main 分支最新 commit 上打正式 tag，确保发布内容为最新。

**自动化发布无需手动操作，只需管理好分支与 tag，GitHub Actions 会自动完成发布。**