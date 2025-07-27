import logging
import sys
from typing import Any, Optional, Callable, TypeVar

T = TypeVar("T")


class _LazyRichConsole:
    """延迟加载的 Rich Console，仅在需要时才初始化"""

    _console: Optional[Any] = None

    def _ensure_console(self) -> None:
        """确保 console 已初始化"""
        if self._console is None:
            try:
                from rich.console import Console

                self._console = Console()
            except ImportError:
                # 如果 rich 不可用，回退到标准输出
                self._console = _StdoutConsole()

    def print(self, *args: Any, **kwargs: Any) -> None:
        """打印到 console"""
        self._ensure_console()
        if self._console is not None:
            self._console.print(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """代理其他方法到实际的 console 对象"""
        self._ensure_console()
        return getattr(self._console, name)


class _StdoutConsole:
    """标准输出 console 作为回退选项"""

    def print(self, *args: Any, **kwargs: Any) -> None:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        print(*args, sep=sep, end=end, file=file)


console = _LazyRichConsole()


class CommandNameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            import click

            ctx = click.get_current_context(silent=True)
            record.command = ctx.info_name if ctx and ctx.info_name else "unknown"
        except Exception:
            record.command = "unknown"
        return True


def _create_logger(name: str = "okit") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s][%(levelname)s][%(command)s] %(message)s",
            datefmt="%y/%m/%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 默认等级，可由主入口动态调整
    if not any(isinstance(f, CommandNameFilter) for f in logger.filters):
        logger.addFilter(CommandNameFilter())
    return logger


class _LazyLogger:
    _real_logger: Optional[logging.Logger] = None

    def _ensure(self) -> None:
        if self._real_logger is None:
            self._real_logger = _create_logger()

    def __getattr__(self, name: str) -> Any:
        self._ensure()
        if self._real_logger is not None:
            return getattr(self._real_logger, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


logger = _LazyLogger()
