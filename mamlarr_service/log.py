from __future__ import annotations

import logging
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class ContextLogger:
    def __init__(self, base_logger: logging.Logger):
        self._base = base_logger

    def _fmt(self, msg: str, context: dict[str, Any]) -> str:
        if context:
            ctx = " ".join(f"{key}={value}" for key, value in context.items())
            return f"{msg} {ctx}"
        return msg

    def debug(self, msg: str, *args: Any, **context: Any):
        self._base.debug(self._fmt(msg, context), *args)

    def info(self, msg: str, *args: Any, **context: Any):
        self._base.info(self._fmt(msg, context), *args)

    def warning(self, msg: str, *args: Any, **context: Any):
        self._base.warning(self._fmt(msg, context), *args)

    def error(self, msg: str, *args: Any, **context: Any):
        self._base.error(self._fmt(msg, context), *args)

    def exception(self, msg: str, *args: Any, **context: Any):
        self._base.exception(self._fmt(msg, context), *args)


logger = ContextLogger(logging.getLogger("mamlarr"))
