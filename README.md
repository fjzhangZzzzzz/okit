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
