# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import sys
from typing import Optional


_LEVEL = os.environ.get("ARCH_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()


def _configure_root_once() -> None:
    root = logging.getLogger("arch_team")
    if getattr(root, "_arch_configured", False):
        return
    level = getattr(logging, _LEVEL, logging.INFO)
    root.setLevel(level)
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(fmt)
    if not root.handlers:
        root.addHandler(handler)
    setattr(root, "_arch_configured", True)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    _configure_root_once()
    if name:
        return logging.getLogger(f"arch_team.{name}")
    return logging.getLogger("arch_team")


def banner(logger: logging.Logger, text: str) -> None:
    line = "=" * len(text)
    logger.info("\n%s\n%s\n%s", line, text, line)


def log_exception(logger: logging.Logger, msg: str, exc: Exception) -> None:
    logger.error("%s: %s", msg, exc, exc_info=True)