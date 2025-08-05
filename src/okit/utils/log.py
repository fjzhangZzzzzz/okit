import logging
import re
import sys
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Dict, List, Union


class OutputLevel(Enum):
    """统一的输出级别，结合了日志级别和用户体验需求"""
    TRACE = 5      # 最详细的调试信息
    DEBUG = 10     # 调试信息
    INFO = 20      # 一般信息
    SUCCESS = 25   # 成功消息（用户友好）
    WARNING = 30   # 警告
    ERROR = 40     # 错误
    CRITICAL = 50  # 严重错误
    QUIET = 60     # 只显示最重要的信息


class RichMarkupProcessor:
    """Rich 标记处理器 - 为不同后端提供格式化兼容性"""
    
    # Rich 标记的正则表达式模式
    RICH_MARKUP_PATTERN = re.compile(r'\[/?(?:bold|italic|underline|strike|reverse|blink|dim|conceal|overline|'
                                     r'red|green|yellow|blue|magenta|cyan|white|black|bright_red|bright_green|'
                                     r'bright_yellow|bright_blue|bright_magenta|bright_cyan|bright_white|'
                                     r'on_red|on_green|on_yellow|on_blue|on_magenta|on_cyan|on_white|on_black|'
                                     r'on_bright_red|on_bright_green|on_bright_yellow|on_bright_blue|'
                                     r'on_bright_magenta|on_bright_cyan|on_bright_white|'
                                     r'#[a-fA-F0-9]{6}|rgb\(\d+,\d+,\d+\))\]')
    
    @classmethod
    def strip_markup(cls, text: str) -> str:
        """移除所有 Rich 格式化标记，返回纯文本"""
        return cls.RICH_MARKUP_PATTERN.sub('', text)
    
    @classmethod
    def has_markup(cls, text: str) -> bool:
        """检查文本是否包含 Rich 格式化标记"""
        return bool(cls.RICH_MARKUP_PATTERN.search(text))
    
    @classmethod
    def convert_to_ansi(cls, text: str) -> str:
        """将 Rich 标记转换为 ANSI 转义序列（简化版本）"""
        # 这是一个简化的转换，可以根据需要扩展
        conversions = {
            '[bold]': '\033[1m',
            '[/bold]': '\033[22m',
            '[red]': '\033[31m',
            '[/red]': '\033[39m',
            '[green]': '\033[32m',
            '[/green]': '\033[39m',
            '[yellow]': '\033[33m',
            '[/yellow]': '\033[39m',
            '[blue]': '\033[34m',
            '[/blue]': '\033[39m',
            '[magenta]': '\033[35m',
            '[/magenta]': '\033[39m',
            '[cyan]': '\033[36m',
            '[/cyan]': '\033[39m',
            '[white]': '\033[37m',
            '[/white]': '\033[39m',
        }
        
        result = text
        for rich_tag, ansi_code in conversions.items():
            result = result.replace(rich_tag, ansi_code)
        
        return result
    
    @classmethod
    def extract_markup_info(cls, text: str) -> Dict[str, Any]:
        """提取文本中的格式化信息，供 GUI 后端使用"""
        markup_info = {
            'plain_text': cls.strip_markup(text),
            'has_formatting': cls.has_markup(text),
            'markup_tags': cls.RICH_MARKUP_PATTERN.findall(text),
            'original_text': text
        }
        return markup_info


@dataclass
class OutputMessage:
    """统一的输出消息结构"""
    level: OutputLevel
    content: Any
    category: str = "general"  # 消息分类：general, progress, result, debug 等
    timestamp: float = None
    metadata: Optional[Dict[str, Any]] = None  # 额外元数据
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def get_formatted_content(self, backend_type: str = "rich") -> str:
        """根据后端类型返回格式化的内容"""
        content_str = str(self.content)
        
        if backend_type == "rich":
            # ConsoleBackend: 保持 Rich 标记不变
            return content_str
        elif backend_type == "plain":
            # LoggingBackend: 移除所有格式化标记
            return RichMarkupProcessor.strip_markup(content_str)
        elif backend_type == "ansi":
            # 支持 ANSI 转义序列的终端
            return RichMarkupProcessor.convert_to_ansi(content_str)
        elif backend_type == "gui":
            # GUIBackend: 返回原始内容，由 GUI 处理格式化
            return content_str
        else:
            # 默认返回纯文本
            return RichMarkupProcessor.strip_markup(content_str)
    
    def get_markup_info(self) -> Dict[str, Any]:
        """获取格式化信息，供 GUI 等后端使用"""
        content_str = str(self.content)
        return RichMarkupProcessor.extract_markup_info(content_str)
    
    def has_formatting(self) -> bool:
        """检查消息内容是否包含格式化标记"""
        content_str = str(self.content)
        return RichMarkupProcessor.has_markup(content_str)


class MessageFilter(ABC):
    """消息过滤器抽象基类"""
    
    @abstractmethod
    def should_output(self, message: OutputMessage) -> bool:
        """判断是否应该输出该消息"""
        pass


class ProgressFilter(MessageFilter):
    """进度消息过滤器 - 避免过于频繁的进度更新"""
    
    def __init__(self, min_interval: float = 0.5):
        self.min_interval = min_interval  # 最小时间间隔（秒）
        self.last_progress_time = 0.0
    
    def should_output(self, message: OutputMessage) -> bool:
        if message.category != "progress":
            return True
        
        current_time = message.timestamp
        if current_time - self.last_progress_time >= self.min_interval:
            self.last_progress_time = current_time
            return True
        
        return False


class CategoryFilter(MessageFilter):
    """基于分类的过滤器"""
    
    def __init__(self, excluded_categories: List[str]):
        self.excluded_categories = set(excluded_categories)
    
    def should_output(self, message: OutputMessage) -> bool:
        return message.category not in self.excluded_categories


class OutputBackend(ABC):
    """输出后端抽象基类"""
    
    def __init__(self):
        self._filters: List[MessageFilter] = []
        self._level = OutputLevel.INFO
    
    def add_filter(self, filter_instance: MessageFilter) -> None:
        """添加消息过滤器"""
        self._filters.append(filter_instance)
    
    def _should_output(self, message: OutputMessage) -> bool:
        """检查是否应该输出消息"""
        # 级别检查
        if message.level.value < self._level.value:
            return False
        
        # 过滤器检查
        for filter_instance in self._filters:
            if not filter_instance.should_output(message):
                return False
        
        return True
    
    @abstractmethod
    def _do_output(self, message: OutputMessage) -> None:
        """实际输出消息的实现"""
        pass
    
    def output(self, message: OutputMessage) -> None:
        """输出消息（带过滤）"""
        if self._should_output(message):
            self._do_output(message)
    
    def set_level(self, level: OutputLevel) -> None:
        """设置输出级别"""
        self._level = level


class ConsoleBackend(OutputBackend):
    """控制台输出后端 - 为CLI优化"""
    
    def __init__(self):
        super().__init__()
        self._console: Optional[Any] = None
        self._ensure_console()

    def _ensure_console(self) -> None:
        """懒加载 Rich Console"""
        if self._console is None:
            try:
                from rich.console import Console
                self._console = Console()
            except ImportError:
                self._console = _StdoutConsole()

    def _do_output(self, message: OutputMessage) -> None:
        """实际输出到控制台"""
        formatted_content = self._format_message(message)
        self._console.print(formatted_content)
    
    def _format_message(self, message: OutputMessage) -> str:
        """根据消息类型格式化输出"""
        # 获取支持 Rich 标记的内容
        content = message.get_formatted_content("rich")
        
        # 对于已包含用户自定义 Rich 标记的内容，优先保持用户格式
        if message.has_formatting():
            # 如果用户已经提供了格式化标记，根据级别只添加必要的前缀
            if message.level == OutputLevel.SUCCESS and not ("[green]✓" in content or "[green]" in content):
                return f"[green]✓[/green] {content}"
            elif message.level == OutputLevel.ERROR and not ("[red]✗" in content or "[red]" in content):
                return f"[red]✗[/red] {content}"
            elif message.level == OutputLevel.WARNING and not ("[yellow]⚠" in content or "[yellow]" in content):
                return f"[yellow]⚠[/yellow] {content}"
            else:
                # 用户已经提供了完整的格式化，直接使用
                return content
        
        # 对于没有用户格式化的内容，使用系统默认格式
        if message.level == OutputLevel.SUCCESS:
            return f"[green]✓ {content}[/green]"
        elif message.level == OutputLevel.ERROR:
            return f"[red]✗ {content}[/red]"
        elif message.level == OutputLevel.WARNING:
            return f"[yellow]⚠ {content}[/yellow]"
        elif message.level == OutputLevel.INFO:
            # 对于用户结果，保持简洁
            if message.category == "result":
                return content
            elif message.category == "progress":
                return f"[cyan]{content}[/cyan]"
            return f"[cyan]{content}[/cyan]"
        elif message.level in [OutputLevel.DEBUG, OutputLevel.TRACE]:
            return f"[dim]{content}[/dim]"
        
        return content


class LoggingBackend(OutputBackend):
    """标准日志后端 - 为调试和文件记录优化"""
    
    def __init__(self, name: str = "okit"):
        super().__init__()
        self._logger = self._create_logger(name)
        
        # 为日志后端添加默认过滤器，避免频繁的进度更新
        self.add_filter(ProgressFilter(min_interval=5.0))  # 5秒间隔记录进度
        self.add_filter(CategoryFilter(["result"]))  # 不记录用户结果到日志
    
    def _create_logger(self, name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(asctime)s][%(levelname)s][%(command)s] %(message)s",
                datefmt="%y/%m/%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.addFilter(CommandNameFilter())
            
        # 重要：防止日志传播到根logger，避免影响其他库
        logger.propagate = False
        return logger
    
    def set_level(self, level: OutputLevel) -> None:
        super().set_level(level)
        # 映射到标准logging级别
        logging_level = min(level.value, 50)  # 限制在CRITICAL以内
        self._logger.setLevel(logging_level)
    
    def _do_output(self, message: OutputMessage) -> None:
        """实际输出到日志"""
        # 获取纯文本内容（移除 Rich 标记）
        content = message.get_formatted_content("plain")
        
        # 添加分类信息到日志
        if message.category != "general":
            content = f"[{message.category}] {content}"
        
        # 映射到标准logging方法
        if message.level.value <= 10:
            self._logger.debug(content)
        elif message.level.value <= 20:
            self._logger.info(content)
        elif message.level.value <= 30:
            self._logger.warning(content)
        elif message.level.value <= 40:
            self._logger.error(content)
        else:
            self._logger.critical(content)


class GUIBackend(OutputBackend):
    """GUI输出后端 - 为未来GUI扩展准备"""
    
    def __init__(self, max_messages: int = 1000):
        super().__init__()
        self.max_messages = max_messages
        self._message_queue: deque = deque(maxlen=max_messages)
    
    def _do_output(self, message: OutputMessage) -> None:
        """实际存储消息到队列"""
        # 使用deque的maxlen自动处理容量限制
        self._message_queue.append(message)
        
        # 这里可以触发GUI更新事件
        # 例如：self._notify_gui_update(message)
    
    def get_messages(self, limit: Optional[int] = None) -> List[OutputMessage]:
        """获取消息供GUI显示"""
        if limit is None:
            return list(self._message_queue)
        else:
            return list(self._message_queue)[-limit:] if limit > 0 else []
    
    def get_messages_by_category(self, category: str, limit: Optional[int] = None) -> List[OutputMessage]:
        """按分类获取消息"""
        filtered = [msg for msg in self._message_queue if msg.category == category]
        if limit is None:
            return filtered
        else:
            return filtered[-limit:] if limit > 0 else []
    
    def clear_messages(self) -> None:
        """清空消息队列"""
        self._message_queue.clear()
    
    def get_queue_info(self) -> Dict[str, Any]:
        """获取队列状态信息"""
        return {
            "current_count": len(self._message_queue),
            "max_capacity": self.max_messages,
            "usage_percent": len(self._message_queue) / self.max_messages * 100
        }
    
    def get_formatted_messages(self, format_type: str = "gui", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取格式化的消息，便于 GUI 显示"""
        messages = self.get_messages(limit)
        formatted_messages = []
        
        for msg in messages:
            formatted_msg = {
                "level": msg.level.name,
                "level_value": msg.level.value,
                "category": msg.category,
                "timestamp": msg.timestamp,
                "content": msg.get_formatted_content(format_type),
                "markup_info": msg.get_markup_info() if msg.has_formatting() else None,
                "metadata": msg.metadata
            }
            formatted_messages.append(formatted_msg)
        
        return formatted_messages


class UnifiedOutput:
    """统一输出管理器"""
    
    def __init__(self):
        self._backends: List[OutputBackend] = []
        self._level = OutputLevel.INFO
        
        # 默认使用控制台后端（CLI友好）
        self.add_backend(ConsoleBackend())
    
    def add_backend(self, backend: OutputBackend) -> None:
        """添加输出后端"""
        self._backends.append(backend)
        backend.set_level(self._level)
    
    def remove_backend(self, backend_type: type) -> None:
        """移除指定类型的后端"""
        self._backends = [b for b in self._backends if not isinstance(b, backend_type)]
    
    def clear_backends(self) -> None:
        """清空所有后端"""
        self._backends = []
    
    def set_level(self, level: OutputLevel) -> None:
        """设置全局输出级别"""
        self._level = level
        for backend in self._backends:
            backend.set_level(level)
    
    def output(self, message: OutputMessage) -> None:
        """向所有后端输出消息"""
        for backend in self._backends:
            backend.output(message)
    
    # 便捷方法
    def success(self, content: Any, category: str = "general") -> None:
        self.output(OutputMessage(OutputLevel.SUCCESS, content, category))
    
    def error(self, content: Any, category: str = "general") -> None:
        self.output(OutputMessage(OutputLevel.ERROR, content, category))
    
    def warning(self, content: Any, category: str = "general") -> None:
        self.output(OutputMessage(OutputLevel.WARNING, content, category))
    
    def info(self, content: Any, category: str = "general") -> None:
        self.output(OutputMessage(OutputLevel.INFO, content, category))
    
    def debug(self, content: Any, category: str = "debug") -> None:
        self.output(OutputMessage(OutputLevel.DEBUG, content, category))
    
    def trace(self, content: Any, category: str = "debug") -> None:
        self.output(OutputMessage(OutputLevel.TRACE, content, category))
    
    def result(self, content: Any) -> None:
        """输出用户结果 - 特殊分类，通常不带装饰"""
        self.output(OutputMessage(OutputLevel.INFO, content, category="result"))
    
    def progress(self, content: Any) -> None:
        """输出进度信息"""
        self.output(OutputMessage(OutputLevel.INFO, content, category="progress"))


class _StdoutConsole:
    """标准输出 console 作为回退选项"""

    def print(self, *args: Any, **kwargs: Any) -> None:
        # 移除 Rich 特定的标记
        import re
        clean_args = []
        for arg in args:
            if isinstance(arg, str):
                # 简单清理 Rich 标记
                clean = re.sub(r'\[/?[^]]+\]', '', str(arg))
                clean_args.append(clean)
            else:
                clean_args.append(arg)
        
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        
        # 处理编码问题
        try:
            print(*clean_args, sep=sep, end=end, file=file)
        except UnicodeEncodeError:
            # 如果遇到编码错误，尝试使用 UTF-8 编码
            try:
                # 重新配置 stdout 为 UTF-8
                import codecs
                if hasattr(sys.stdout, 'reconfigure'):
                    sys.stdout.reconfigure(encoding='utf-8')
                print(*clean_args, sep=sep, end=end, file=file)
            except Exception:
                # 最后的回退：移除所有 Unicode 字符
                safe_args = []
                for arg in clean_args:
                    if isinstance(arg, str):
                        # 移除所有非 ASCII 字符
                        safe_arg = ''.join(c for c in arg if ord(c) < 128)
                        safe_args.append(safe_arg)
                    else:
                        safe_args.append(arg)
                print(*safe_args, sep=sep, end=end, file=file)


class CommandNameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            import click
            ctx = click.get_current_context(silent=True)
            record.command = ctx.info_name if ctx and ctx.info_name else "unknown"
        except Exception:
            record.command = "unknown"
        return True


# 全局实例
output = UnifiedOutput()

# 便捷函数用于特殊场景
def setup_gui_mode(max_messages: int = 1000):
    """切换到GUI模式"""
    output.remove_backend(ConsoleBackend)
    output.add_backend(GUIBackend(max_messages=max_messages))

def setup_file_logging(log_file: str):
    """添加文件日志记录"""
    file_backend = LoggingBackend()
    # 这里可以添加文件处理器到file_backend._logger
    output.add_backend(file_backend)

def setup_dual_mode(max_gui_messages: int = 1000):
    """设置控制台+GUI双模式"""
    output.add_backend(GUIBackend(max_messages=max_gui_messages))

def set_quiet_mode():
    """设置安静模式 - 只显示重要信息"""
    output.set_level(OutputLevel.QUIET)

def set_verbose_mode():
    """设置详细模式 - 显示调试信息"""
    output.set_level(OutputLevel.DEBUG)

def configure_output_level(level_name: str):
    """根据字符串配置输出级别"""
    level_map = {
        "TRACE": OutputLevel.TRACE,
        "DEBUG": OutputLevel.DEBUG,
        "INFO": OutputLevel.INFO,
        "WARNING": OutputLevel.WARNING,
        "ERROR": OutputLevel.ERROR,
        "CRITICAL": OutputLevel.CRITICAL,
        "QUIET": OutputLevel.QUIET,
    }
    level = level_map.get(level_name.upper(), OutputLevel.INFO)
    output.set_level(level)

def map_logging_level_to_output_level(logging_level: str) -> OutputLevel:
    """将标准logging级别映射到OutputLevel"""
    mapping = {
        "DEBUG": OutputLevel.DEBUG,
        "INFO": OutputLevel.INFO,
        "WARNING": OutputLevel.WARNING,
        "ERROR": OutputLevel.ERROR,
        "CRITICAL": OutputLevel.CRITICAL,
    }
    return mapping.get(logging_level.upper(), OutputLevel.INFO)
