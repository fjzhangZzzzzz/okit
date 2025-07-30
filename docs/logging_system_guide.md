# OKIT 统一输出系统使用指南

## 概述

OKIT 采用了全新的统一输出系统，既保持了CLI的优秀用户体验，又具备了日志级别控制和未来GUI扩展的能力。该系统解决了原有日志输出格式不一致的问题，并提供了强大的扩展性。

## 设计特点

### 1. 统一的输出接口
- 同时支持用户友好的控制台输出和标准的日志记录
- 可以同时向多个后端输出（控制台、文件、GUI等）
- 简洁直观的API，易于使用和维护

### 2. 丰富的输出级别
```python
from okit.utils.log import OutputLevel

# 可用级别
OutputLevel.TRACE     # 5  - 最详细的调试信息
OutputLevel.DEBUG     # 10 - 调试信息
OutputLevel.INFO      # 20 - 一般信息
OutputLevel.SUCCESS   # 25 - 成功消息（用户友好）
OutputLevel.WARNING   # 30 - 警告
OutputLevel.ERROR     # 40 - 错误
OutputLevel.CRITICAL  # 50 - 严重错误
OutputLevel.QUIET     # 60 - 只显示最重要的信息
```

### 3. 智能的消息过滤
- **进度过滤**: 避免过于频繁的进度更新影响性能
- **分类过滤**: 不同后端可以选择性显示不同类型的消息
- **自定义过滤器**: 可以添加自定义的过滤逻辑

### 4. 多种输出后端
- **ConsoleBackend**: CLI用户体验优化，支持彩色输出和图标
- **LoggingBackend**: 标准日志格式，适合调试和文件记录，自动过滤高频消息
- **GUIBackend**: 为未来GUI扩展准备，带有内存管理

## 使用方法

### 基本使用

```python
from okit.utils.log import output

# 使用语义化的方法
output.success("操作成功完成")        # [green]✓ 操作成功完成[/green]
output.error("操作失败")             # [red]✗ 操作失败[/red]
output.warning("请注意")             # [yellow]⚠ 请注意[/yellow]
output.info("一般信息")              # [cyan]一般信息[/cyan]
output.debug("调试信息")             # [dim]调试信息[/dim]

# 特殊分类
output.result("用户查询结果")         # 纯文本输出，不带装饰
output.progress("正在处理...")        # 进度信息（会被智能过滤）
```

### 级别控制

```python
from okit.utils.log import output, OutputLevel, configure_output_level

# 设置输出级别
output.set_level(OutputLevel.WARNING)  # 只显示警告及以上级别

# 或使用字符串配置
configure_output_level("DEBUG")        # 显示所有调试信息
configure_output_level("QUIET")        # 只显示最重要的信息
```

### CLI集成

```bash
# 详细输出
okit tool-name --verbose
okit tool-name --log-level DEBUG

# 安静模式
okit tool-name --quiet
okit tool-name --log-level QUIET

# 追踪级别（最详细）
okit tool-name --log-level TRACE
```

## 高级特性

### 1. Rich 格式化兼容性

#### 自定义格式化支持

新的日志系统提供了对 Rich 标记的完整兼容性支持，工具脚本可以使用自定义的格式化标记：

```python
# 用户可以直接使用 Rich 标记
output.result("[bold]配置文件路径:[/bold] /home/user/.config")
output.success("[green]✓ 操作成功![/green]") 
output.warning("[yellow]⚠ 注意事项[/yellow]")
output.error("[red]✗ 连接失败[/red]")
```

#### 多后端格式化处理

不同后端会智能处理格式化标记：

- **ConsoleBackend**: 保持 Rich 标记，支持彩色输出和样式
- **LoggingBackend**: 自动移除格式化标记，输出纯文本到日志文件
- **GUIBackend**: 保留格式化信息供 GUI 组件使用

#### 格式化处理器 API

`RichMarkupProcessor` 提供了灵活的格式化处理：

```python
from okit.utils.log import RichMarkupProcessor

# 检测是否包含格式化
has_formatting = RichMarkupProcessor.has_markup("[bold]text[/bold]")

# 移除所有格式化标记
plain_text = RichMarkupProcessor.strip_markup("[red]Error[/red]")

# 转换为 ANSI 转义序列
ansi_text = RichMarkupProcessor.convert_to_ansi("[bold]text[/bold]")

# 提取格式化信息
markup_info = RichMarkupProcessor.extract_markup_info("[green]Success[/green]")
```

#### OutputMessage 格式化方法

`OutputMessage` 对象提供了便利的格式化方法：

```python
message = OutputMessage(OutputLevel.INFO, "[bold]Important[/bold]", "general")

# 获取不同格式的内容
rich_content = message.get_formatted_content("rich")      # 保持 Rich 标记
plain_content = message.get_formatted_content("plain")    # 纯文本
ansi_content = message.get_formatted_content("ansi")      # ANSI 转义序列
gui_content = message.get_formatted_content("gui")        # GUI 原始格式

# 检查和获取格式化信息
has_formatting = message.has_formatting()
markup_info = message.get_markup_info()
```

### 2. 智能进度过滤

LoggingBackend 自动过滤高频的进度更新：

```python
# 这些进度消息在控制台会全部显示
# 但在日志文件中会按5秒间隔记录
for i in range(100):
    output.progress(f"Processing {i+1}/100")
```

### 3. 内存管理的GUI后端

```python
from okit.utils.log import setup_gui_mode

# GUI后端自动限制消息数量，防止内存泄漏
setup_gui_mode(max_messages=2000)  # 最多保留2000条消息

# 获取队列状态
gui_backend = next(b for b in output._backends if isinstance(b, GUIBackend))
status = gui_backend.get_queue_info()
# {'current_count': 150, 'max_capacity': 2000, 'usage_percent': 7.5}
```

### 4. 自定义过滤器

```python
from okit.utils.log import MessageFilter, output

class VerboseFilter(MessageFilter):
    """只在详细模式下显示特定消息"""
    
    def __init__(self, verbose: bool):
        self.verbose = verbose
    
    def should_output(self, message: OutputMessage) -> bool:
        if message.category == "verbose" and not self.verbose:
            return False
        return True

# 为特定后端添加过滤器
console_backend = next(b for b in output._backends if isinstance(b, ConsoleBackend))
console_backend.add_filter(VerboseFilter(verbose=True))
```

## 最佳实践

### 1. 按场景选择输出方法

```python
from okit.utils.log import output

# ✅ 用户操作结果
output.success("文件上传成功")
output.error("连接失败")

# ✅ 系统状态信息
output.info("服务已启动")
output.warning("磁盘空间不足")

# ✅ 用户查询结果（保持纯净）
output.result(formatted_table)
output.result("配置值: some_value")

# ✅ 进度显示（会被智能过滤）
output.progress("下载进度: 45%")

# ✅ 调试信息
output.debug("API调用参数", category="api")
output.trace("详细的内部状态", category="internal")
```

### 2. 错误处理模式

```python
import traceback

try:
    risky_operation()
    output.success("操作成功完成")
except ValueError as e:
    output.error(f"参数错误: {e}")
    output.debug(f"详细错误: {traceback.format_exc()}")
except Exception as e:
    output.error(f"操作失败: {e}")
    output.debug(f"异常堆栈: {traceback.format_exc()}")
```

### 3. 工具脚本迁移模式

```python
# 旧的混合使用方式 ❌
# from okit.utils.log import logger, console
# logger.info("开始处理")
# console.print("[green]处理完成[/green]")

# 新的统一方式 ✅
from okit.utils.log import output

output.debug("开始处理")  # 内部日志
output.success("处理完成")  # 用户反馈
```

## 后端差异化处理

### ConsoleBackend
- 显示所有用户相关消息
- 彩色格式和图标
- 进度信息实时显示

### LoggingBackend
- 自动过滤高频进度消息（5秒间隔）
- 不记录用户结果（result类别）
- 添加分类标签到日志

### GUIBackend
- 自动内存管理（默认1000条消息）
- 支持按分类获取消息
- 提供队列状态监控

## 扩展功能

### GUI模式

```python
from okit.utils.log import setup_gui_mode, output

# 切换到GUI模式
setup_gui_mode(max_messages=2000)

# 获取消息用于GUI显示
gui_backend = next(b for b in output._backends if isinstance(b, GUIBackend))
all_messages = gui_backend.get_messages()
error_messages = gui_backend.get_messages_by_category("error")
```

### 双模式（控制台+GUI）

```python
from okit.utils.log import setup_dual_mode

# 同时输出到控制台和GUI
setup_dual_mode(max_gui_messages=1000)
```

### 文件日志

```python
from okit.utils.log import setup_file_logging

# 添加文件日志记录
setup_file_logging("/path/to/logfile.log")
```

## 性能优化

1. **进度消息过滤**: LoggingBackend自动限制进度消息频率
2. **内存限制**: GUIBackend使用deque自动管理内存
3. **延迟初始化**: Rich Console只在需要时才初始化
4. **智能分类**: 不同类型的消息采用不同的处理策略

## 配置示例

### 开发环境

```python
# 显示所有调试信息
configure_output_level("DEBUG")
```

### 生产环境

```python
# 只显示重要信息
configure_output_level("INFO")
setup_file_logging("/var/log/okit.log")
```

### GUI应用

```python
# GUI模式，保留更多历史消息
setup_gui_mode(max_messages=5000)
configure_output_level("INFO")
```

## 总结

改进后的统一输出系统具有以下优势：

1. **解决了原有问题**：
   - 消息格式统一一致
   - 支持级别控制
   - 不同后端智能过滤

2. **提升了性能**：
   - 进度消息智能过滤
   - GUI内存自动管理
   - 延迟初始化机制

3. **增强了扩展性**：
   - 插件式后端架构
   - 自定义过滤器支持
   - 未来GUI无缝集成

4. **改善了开发体验**：
   - 简洁直观的API
   - 语义化的方法名
   - 完全向前兼容

这个设计既解决了当前CLI工具的痛点，又为未来的GUI扩展提供了坚实的基础。 