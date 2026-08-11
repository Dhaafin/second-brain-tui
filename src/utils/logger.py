"""Logger Utility — Sets up global logging and uncaught exception handlers."""

import logging
import os
import sys
from pathlib import Path


def setup_logging() -> None:
    """Configure global logging and intercept uncaught exceptions."""
    log_dir = Path(".agents/logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path(".")

    log_file = log_dir / "tui_app.log"

    # Configure root logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    # Set up global exception handler
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger("sys").critical(
            "Uncaught runtime exception occurred",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception
    logging.getLogger("second_brain").info(
        "Logger initialized. Writing logs to: %s", log_file
    )
