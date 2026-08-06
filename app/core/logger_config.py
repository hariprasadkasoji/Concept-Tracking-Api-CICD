import logging
import os
import shutil
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
pid = os.getpid()


def get_log_directory() -> Path:
    """
    Determine the logs folder.

    Priority:
    1. settings.LOG_DIR as application root
       -> creates <LOG_DIR>/logs
    2. <project_root>/logs
    """

    default_log_dir = (
        Path(__file__).resolve().parent.parent.parent / "logs"
    )

    custom_base_dir = settings.LOG_DIR

    if custom_base_dir:
        try:
            # LOG_DIR is the application root folder
            logs_dir = (
                Path(custom_base_dir)
                .expanduser()
                .resolve()
                / "logs"
            )

            logs_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            # Verify write access
            test_file = logs_dir / ".write_test"
            test_file.touch(exist_ok=True)
            test_file.unlink()

            return logs_dir

        except Exception:
            pass

    default_log_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return default_log_dir


def cleanup_old_logs(
    log_dir: Path,
    retention_days: int = 5
) -> None:
    """
    Delete log files older than retention_days.
    """

    if not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    for log_file in log_dir.glob("*.log"):

        try:
            modified_time = datetime.fromtimestamp(
                log_file.stat().st_mtime
            )

            if modified_time < cutoff:
                log_file.unlink()

        except Exception:
            continue

# Create logs folder
LOG_DIR = get_log_directory()


# Remove old log files
cleanup_old_logs(
    LOG_DIR,
    settings.LOG_RETENTION_DAYS
)


# Create log files inside logs folder
APP_LOG_FILE = LOG_DIR / f"app_{timestamp}_{pid}.log"


# Third-party loggers that are extremely chatty at DEBUG level and are
# almost never useful for diagnosing OUR application's behavior. Each of
# these propagates to the root logger by default, so without this list
# every TCP connect / TLS handshake / raw HTTP header dump from outbound
# calls (e.g. the MSAL/Azure AD token exchange) gets written to our app
# log file whenever ENVIRONMENT=DEVELOPMENT sets root to DEBUG.
NOISY_LOGGERS = [
    "httpx",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "asyncio",
    "urllib3",
    "azure",
    "msal",
]


def setup_logging():

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    )

    app_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )

    app_handler.setFormatter(formatter)

    root_logger = logging.getLogger()

    # Prevent duplicate handlers
    if root_logger.handlers:
        root_logger.handlers.clear()

    if settings.ENVIRONMENT == "DEVELOPMENT":

        root_logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        root_logger.addHandler(console_handler)

    else:
        root_logger.setLevel(logging.INFO)

    root_logger.addHandler(app_handler)

    # Silence noisy loggers - these still work normally (WARNING/ERROR
    # from them will still surface), they just won't flood the log with
    # DEBUG/INFO-level connection tracing and raw request/response dumps.
    logging.getLogger("uvicorn.access").disabled = True

    for noisy_logger_name in NOISY_LOGGERS:
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)