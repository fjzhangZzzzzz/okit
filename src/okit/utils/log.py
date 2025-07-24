from rich.console import Console
from rich.logging import RichHandler
import logging

console = Console()

class CommandNameFilter(logging.Filter):
    def filter(self, record):
        try:
            import click
            ctx = click.get_current_context(silent=True)
            record.command = ctx.info_name if ctx and ctx.info_name else "unknown"
        except Exception:
            record.command = "unknown"
        return True

def get_logger(name="okit"):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = RichHandler(console=console, show_time=True, omit_repeated_times=False, log_time_format="[%y/%m/%d %H:%M:%S]", show_level=True, show_path=False)
        formatter = logging.Formatter("%(command)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 默认等级，可由主入口动态调整
    # 只添加一次 filter
    if not any(isinstance(f, CommandNameFilter) for f in logger.filters):
        logger.addFilter(CommandNameFilter())
    return logger

logger = get_logger()