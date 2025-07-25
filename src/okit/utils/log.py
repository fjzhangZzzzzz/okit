import logging
import sys

class _StdoutConsole:
    def print(self, *args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        file = kwargs.get('file', sys.stdout)
        print(*args, sep=sep, end=end, file=file)

console = _StdoutConsole()

class CommandNameFilter(logging.Filter):
    def filter(self, record):
        try:
            import click
            ctx = click.get_current_context(silent=True)
            record.command = ctx.info_name if ctx and ctx.info_name else "unknown"
        except Exception:
            record.command = "unknown"
        return True

def _create_logger(name="okit"):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(command)s] %(message)s", datefmt="%y/%m/%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 默认等级，可由主入口动态调整
    if not any(isinstance(f, CommandNameFilter) for f in logger.filters):
        logger.addFilter(CommandNameFilter())
    return logger

class _LazyLogger:
    _real_logger = None
    def _ensure(self):
        if self._real_logger is None:
            self._real_logger = _create_logger()
    def __getattr__(self, name):
        self._ensure()
        return getattr(self._real_logger, name)

logger = _LazyLogger()