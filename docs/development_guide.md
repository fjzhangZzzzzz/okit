# 开发指导

本指南介绍如何为 okit 项目开发工具脚本，包括架构设计、开发流程、配置管理等。

## 架构设计

### 源码目录结构

```
okit/
  ├── cli/           # 命令行入口
  ├── core/          # 核心框架
  ├── tools/         # 工具脚本
  ├── utils/         # 通用工具函数
  └── __init__.py
```

### 自动注册机制

命令行入口会自动扫描 `tools/` 目录下的脚本，自动导入并注册 CLI 命令。

## 工具脚本开发

### 基础开发模式

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

### 命令模式选择

根据工具的复杂度，可以选择两种命令模式：

#### 1. 复杂命令模式（使用子命令）

适用于有多个功能模块的工具，如配置管理、数据操作、状态查询等：

```python
@okit_tool("complex_tool", "Complex tool with multiple features")
class ComplexTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        @click.option('--key', required=True)
        @click.option('--value')
        def config(key: str, value: str):
            """配置管理命令"""
            pass
        
        @cli_group.command()
        def status():
            """状态查询命令"""
            pass
        
        @cli_group.command()
        def backup():
            """备份命令"""
            pass
```

**使用方式**：
```bash
okit complex_tool config --key api_url --value https://api.example.com
okit complex_tool status
okit complex_tool backup
```

#### 2. 简单命令模式（直接调用）

适用于单一功能的工具，如文件同步、数据处理等：

```python
@okit_tool("simple_tool", "Simple tool with single function", use_subcommands=False)
class SimpleTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        @click.option('--host', required=True)
        @click.option('--user', required=True)
        @click.option('--source', required=True)
        def main(host: str, user: str, source: str):
            """主要功能命令"""
            pass
```

**使用方式**：
```bash
okit simple_tool --host server.com --user admin --source /path/to/files
```

#### 模式选择指南

**何时使用子命令模式（默认）**：
- 工具有多个独立的功能模块
- 需要不同的参数组合
- 用户需要明确选择操作类型
- 例如：配置管理、状态查询、备份恢复等

**何时使用直接调用模式**：
- 工具只有单一主要功能
- 参数相对固定
- 用户希望简化调用
- 例如：文件同步、数据处理、简单转换等

#### 技术实现

- **子命令模式**：`use_subcommands=True`（默认）
  - 创建 `click.Group`
  - 用户需要指定子命令：`okit tool subcommand --options`

- **直接调用模式**：`use_subcommands=False`
  - 创建 `click.Command`
  - 用户直接调用：`okit tool --options`

#### 实际示例

**复杂命令示例**（`shellconfig.py`）：
```python
@okit_tool("shellconfig", "Shell configuration management tool")
class ShellConfig(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def sync():
            """同步配置"""
            pass
        
        @cli_group.command()
        def status():
            """查看状态"""
            pass
```

**简单命令示例**（`gitdiffsync.py`）：
```python
@okit_tool("gitdiffsync", "Git project synchronization tool", use_subcommands=False)
class GitDiffSync(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        @click.option('--host', required=True)
        @click.option('--user', required=True)
        def main(host: str, user: str):
            """同步 Git 项目"""
            pass
```

### 日志输出

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

## 配置和数据管理

BaseTool 提供了完整的配置和数据管理功能，每个工具都有独立的配置和数据目录。

### 目录结构

```
~/.okit/
├── config/           # 配置目录
│   ├── tool1/       # 工具1的配置
│   │   └── config.yaml
│   └── tool2/       # 工具2的配置
│       └── config.yaml
└── data/            # 数据目录
    ├── tool1/       # 工具1的数据
    │   ├── cache/
    │   ├── logs/
    │   └── backups/
    └── tool2/       # 工具2的数据
        ├── downloads/
        └── temp/
```

### 配置管理接口

#### 基础配置操作

```python
class MyTool(BaseTool):
    def some_method(self):
        # 获取配置目录
        config_dir = self.get_config_path()
        
        # 获取配置文件路径（默认使用 config.yaml）
        config_file = self.get_config_file()
        
        # 加载配置
        config = self.load_config({"default": "value"})
        
        # 保存配置
        self.save_config({"key": "value"})
        
        # 检查配置是否存在
        if self.has_config():
            print("配置文件存在")
```

#### 配置值操作

```python
# 获取配置值（支持嵌套键）
value = self.get_config_value("database.host", "localhost")
value = self.get_config_value("api.timeout", 30)

# 设置配置值（支持嵌套键）
self.set_config_value("database.host", "127.0.0.1")
self.set_config_value("api.timeout", 60)
```

#### 配置格式

工具脚本默认使用 YAML 格式的配置文件（`config.yaml`），无需关心文件格式和路径：

```python
# 自动使用 config.yaml
config = self.load_config()
self.save_config(config)

# 支持嵌套键访问
host = self.get_config_value("database.host", "localhost")
self.set_config_value("api.timeout", 60)
```

**注意**：配置文件使用 `ruamel.yaml` 库处理，提供更好的 YAML 支持和维护。

### 数据管理接口

#### 数据目录操作

```python
# 获取数据目录
data_dir = self.get_data_path()

# 获取数据文件路径
cache_file = self.get_data_file("cache", "temp", "file.txt")

# 确保数据目录存在
self.ensure_data_dir("cache", "temp")

# 列出数据文件
files = self.list_data_files("cache")

# 清理数据
self.cleanup_data("temp", "old_file.txt")
```

#### 数据组织示例

```python
class MyTool(BaseTool):
    def download_file(self, url: str):
        # 确保下载目录存在
        download_dir = self.ensure_data_dir("downloads")
        
        # 保存下载的文件
        file_path = self.get_data_file("downloads", "file.txt")
        # ... 下载逻辑
        
    def create_backup(self):
        # 备份到数据目录
        backup_dir = self.ensure_data_dir("backups")
        # ... 备份逻辑
```

### 高级功能

#### 配置备份和恢复

```python
# 备份配置
backup_path = self.backup_config()
if backup_path:
    print(f"配置已备份到: {backup_path}")

# 恢复配置
self.restore_config(backup_path)
```

#### 配置迁移

```python
class MyTool(BaseTool):
    def migrate_config(self, old_version: str, new_version: str) -> bool:
        """自定义配置迁移逻辑"""
        if old_version == "1.0" and new_version == "2.0":
            # 迁移逻辑
            old_config = self.load_config()
            new_config = self._migrate_v1_to_v2(old_config)
            self.save_config(new_config)
            return True
        return False
```

## 开发环境搭建

### 环境准备

```bash
git clone https://github.com/fjzhangZzzzzz/okit.git
cd okit

# 修改代码

# 本地构建 okit
uv build .

# 本地安装 okit
uv tool install -e . --reinstall
```

### 发布流程

```bash
# 发布到 TestPyPI
uv publish --index testpypi --token YOUR_TEST_TOKEN

# 发布到 PyPI
uv publish --token YOUR_PYPI_TOKEN

# 从 TestPyPI 安装（需指定索引）
uv tool install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple okit==1.0.1b6

# 从正式 PyPI 安装
uv tool install okit
```

## 使用示例

### 完整的工具示例

```python
@okit_tool("example", "Example Tool")
class ExampleTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        @click.option('--key', required=True)
        @click.option('--value')
        def config(key: str, value: str):
            if value:
                # 设置配置
                self.set_config_value(key, value)
                console.print(f"设置 {key} = {value}")
            else:
                # 读取配置
                value = self.get_config_value(key, "未设置")
                console.print(f"{key}: {value}")
        
        @cli_group.command()
        def info():
            # 显示工具信息
            info = self.get_tool_info()
            console.print(f"配置目录: {info['config_path']}")
            console.print(f"数据目录: {info['data_path']}")
```

### 简单命令示例

```python
@okit_tool("simple_example", "Simple Example Tool", use_subcommands=False)
class SimpleExampleTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        @click.option('--input', required=True, help='Input file path')
        @click.option('--output', required=True, help='Output file path')
        @click.option('--format', default='json', help='Output format')
        def main(input: str, output: str, format: str):
            """处理文件的主要功能"""
            # 读取输入文件
            with open(input, 'r') as f:
                data = f.read()
            
            # 处理数据
            processed_data = self._process_data(data, format)
            
            # 保存输出
            with open(output, 'w') as f:
                f.write(processed_data)
            
            console.print(f"[green]处理完成: {input} -> {output}[/green]")
    
    def _process_data(self, data: str, format: str) -> str:
        """数据处理逻辑"""
        # 实际的数据处理代码
        return f"Processed data in {format} format: {data}"
```

**使用方式对比**：

复杂命令模式：
```bash
okit example config --key api_url --value https://api.example.com
okit example info
```

简单命令模式：
```bash
okit simple_example --input data.txt --output result.json --format json
```

### 配置验证

```python
def validate_config(self) -> bool:
    """验证工具配置"""
    # 检查必需配置
    required_keys = ["api_key", "base_url"]
    for key in required_keys:
        if not self.get_config_value(key):
            self.logger.error(f"缺少必需配置: {key}")
            return False
    
    return True
```

## 工具信息

每个工具都可以通过 `get_tool_info()` 获取完整信息：

```python
info = tool.get_tool_info()
# 返回：
# {
#     "name": "tool_name",
#     "description": "tool description", 
#     "start_time": "2024-01-01T00:00:00",
#     "config_path": "/home/user/.okit/config/tool_name",
#     "data_path": "/home/user/.okit/data/tool_name"
# }
```

## 版本号规约

### 版本号核心
采用语义化版本，符合 PEP 440，遵循格式 `[主版本号]!.[次版本号].[修订号][扩展标识符]`
- 主版本号（Major）：重大变更（如 API 不兼容更新），递增时重置次版本和修订号。
- 次版本号（Minor）：向后兼容的功能性更新，递增时重置修订号。
- 修订号（Micro）：向后兼容的 Bug 修复或小改动。

### 扩展标识符（可选）
- 开发版，格式示例 `1.0.0.dev1`
- Alpha 预发布，格式示例 `1.0.0a1`，内部测试
- Beta 预发布，格式示例 `1.0.0b2`，公开测试
- RC 预发布，格式示例 `1.0.0rc3`，候选发布
- 正式版，格式示例 `1.0.0`，正式发布，稳定可用
- 后发布版，格式示例 `1.0.0.post1`，修正补丁

## 自动化发布流程

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

## 性能监控与优化

okit 提供了内置的零侵入性性能监控框架，帮助开发者快速定位CLI冷启动性能瓶颈，优化工具脚本的加载速度。

### 性能监控功能

性能监控框架具有以下特性：

- **零侵入性**：不需要修改任何现有工具代码
- **精确追踪**：追踪模块导入、装饰器执行、命令注册等各个阶段
- **智能分析**：自动识别性能瓶颈并提供优化建议
- **多种输出**：支持控制台和JSON格式输出
- **依赖分析**：构建模块导入依赖树，帮助理解性能影响
- **模块化设计**：性能监控逻辑集中在 `okit.utils.perf_monitor` 模块中，主CLI保持简洁

### 启用性能监控

#### 环境变量方式

```bash
# 基础监控 - 控制台输出
OKIT_PERF_MONITOR=basic okit --help
OKIT_PERF_MONITOR=basic okit your_tool --help

# 详细监控 - 详细分析
OKIT_PERF_MONITOR=detailed okit your_tool command

# JSON格式输出
OKIT_PERF_MONITOR=json okit your_tool command

# 保存监控结果到文件
OKIT_PERF_MONITOR=json OKIT_PERF_OUTPUT=perf_report.json okit your_tool command
```

#### CLI参数方式

```bash
# 基础监控
okit --perf-monitor=basic your_tool command

# 详细监控
okit --perf-monitor=detailed your_tool command  

# JSON输出并保存到文件
okit --perf-monitor=json --perf-output=report.json your_tool command
```

### 监控输出格式

#### 控制台输出示例

```
🚀 OKIT Performance Report
==================================================
Total CLI initialization: 825ms ✗

📊 Phase Breakdown:
   ├─ Module Imports            2ms ( 0.2%) ░░░░░░░░░░░░░░░
   ├─ Decorator Execution      26ms ( 3.1%) ░░░░░░░░░░░░░░░
   ├─ Command Registration      1ms ( 0.1%) ░░░░░░░░░░░░░░░
   ├─ Other                   796ms (96.5%) ██████████████░

🔍 Tool-level Breakdown:
   1. mobaxterm_pro        345ms (28.0%) [SLOW]
   2. shellconfig          234ms (19.0%) [MEDIUM]  
   3. gitdiffsync          123ms (10.0%) [OK]
   4. pedump                89ms ( 7.2%) [OK]

⚡ Performance Insights:
   • mobaxterm_pro is slow (345ms) - slow_import
   • shellconfig has heavy Git operations (89ms decorator time)
   • 3 tools are below 100ms threshold ✓

💡 Optimization Recommendations:
   1. Consider lazy loading of cryptography in mobaxterm_pro
   2. Cache Git repository initialization in shellconfig
   3. Implement deferred loading for heavy modules

🎯 Target: Reduce to <300ms (current: 825ms, need: -525ms)
```

#### JSON输出格式

```json
{
  "total_time": 0.825,
  "phases": {
    "module_imports": 0.002,
    "decorator_execution": 0.026,
    "command_registration": 0.001,
    "other": 0.796
  },
  "tools": {
    "mobaxterm_pro": {
      "import_time": 0.345,
      "decorator_time": 0.012,
      "total_time": 0.357
    }
  },
  "import_times": {
    "okit.tools.mobaxterm_pro": 0.345,
    "okit.tools.shellconfig": 0.234
  },
  "dependency_tree": {
    "okit.tools.mobaxterm_pro": ["cryptography", "winreg"]
  },
  "bottlenecks": [
    {
      "type": "slow_import",
      "module": "okit.tools.mobaxterm_pro",
      "time": 0.345,
      "severity": "high"
    }
  ],
  "recommendations": [
    "Consider lazy loading of cryptography in mobaxterm_pro"
  ],
  "performance_score": 36.4,
  "target_time": 0.3,
  "status": "needs_improvement"
}
```

### 监控数据解读

#### 时间阶段分析

- **Module Imports**: 模块导入时间，包括所有okit工具的导入
- **Decorator Execution**: `@okit_tool`装饰器执行时间
- **Command Registration**: CLI命令注册时间
- **Other**: 其他操作时间（Python解释器启动、依赖解析等）

#### 性能状态指示

- **FAST** (< 50ms): 性能优秀
- **OK** (50-100ms): 性能良好
- **MEDIUM** (100-200ms): 性能一般，可优化
- **SLOW** (> 200ms): 性能较差，需要优化

#### 性能评分

- **90-100分**: 优秀（≤ 300ms）
- **70-89分**: 良好（300-600ms）
- **50-69分**: 一般（600-900ms）
- **< 50分**: 需要改进（> 900ms）

### 开发过程中的性能监控

#### 新工具开发时

```bash
# 开发新工具时监控性能影响
OKIT_PERF_MONITOR=detailed okit your_new_tool --help

# 对比添加新工具前后的性能变化
OKIT_PERF_MONITOR=json OKIT_PERF_OUTPUT=before.json okit --help
# 添加新工具后
OKIT_PERF_MONITOR=json OKIT_PERF_OUTPUT=after.json okit --help
```

#### 持续性能监控

```bash
# 在CI/CD中集成性能监控
OKIT_PERF_MONITOR=json OKIT_PERF_OUTPUT=ci_perf_report.json okit --help

# 定期性能基准测试
OKIT_PERF_MONITOR=detailed okit --help > weekly_perf_report.txt
```

### 性能优化策略

#### 1. 延迟导入优化

对于包含重型依赖的工具，使用延迟导入：

```python
@okit_tool("heavy_tool", "Tool with heavy dependencies")
class HeavyTool(BaseTool):
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def process():
            # 在实际使用时才导入重型依赖
            import heavy_library
            heavy_library.process()
```

#### 2. 缓存机制

```python
# 缓存重复计算结果
@lru_cache(maxsize=1)
def get_expensive_config():
    # 昂贵的配置计算
    return expensive_computation()
```

#### 3. 条件导入

```python
# 只在特定条件下导入
def import_optional_dependency():
    try:
        import optional_library
        return optional_library
    except ImportError:
        return None
```

#### 4. 模块级别优化

- 避免在模块顶层执行重型操作
- 将重型初始化移到函数内部
- 使用`__all__`控制导出内容

### 性能监控最佳实践

1. **定期监控**：在开发过程中定期检查性能变化
2. **基准对比**：建立性能基准，对比新功能的性能影响
3. **目标导向**：以300ms为目标，持续优化冷启动时间
4. **数据驱动**：基于监控数据做优化决策，而非猜测
5. **CI集成**：在持续集成中加入性能监控，防止性能回退
6. **文档记录**：记录性能优化措施和效果，便于团队协作

### 性能监控架构

性能监控框架采用模块化设计：

- **主要模块**：`src/okit/utils/perf_monitor.py` - 包含所有性能监控核心逻辑
- **CLI集成**：`src/okit/cli/main.py` - 仅保留最小化的初始化调用
- **报告生成**：`src/okit/utils/perf_report.py` - 负责格式化输出和分析
- **时间工具**：`src/okit/utils/timing.py` - 提供通用的计时功能

**设计优势**：
- CLI主模块保持简洁和高可读性
- 性能监控逻辑高度内聚，便于维护
- 支持配置优先级：CLI参数 > 环境变量 > 默认值
- 自动处理重复输出问题，确保每次运行只输出一次报告

### 常见性能问题及解决方案

#### 问题1：模块导入耗时过长

**现象**: `Module Imports`占比过高（> 10%）

**解决方案**:
- 使用延迟导入
- 移除不必要的依赖
- 优化导入链

#### 问题2：装饰器执行缓慢

**现象**: `Decorator Execution`时间过长

**解决方案**:
- 简化装饰器逻辑
- 避免在装饰器中执行重型操作
- 缓存装饰器计算结果

#### 问题3：整体启动时间过长

**现象**: `Other`时间占比过高（> 90%）

**解决方案**:
- 检查Python环境配置
- 减少全局变量初始化
- 优化模块组织结构

## 最佳实践

1. **配置默认值**：总是为配置提供合理的默认值
2. **配置验证**：在 `validate_config()` 中验证配置完整性
3. **错误处理**：妥善处理配置读写错误
4. **数据隔离**：每个工具使用独立的数据目录
5. **备份策略**：重要配置定期备份
6. **日志记录**：记录配置操作日志
7. **代码规范**：遵循项目代码风格和命名规范
8. **测试覆盖**：为工具功能编写测试用例
9. **文档完善**：为工具提供清晰的文档和使用示例 