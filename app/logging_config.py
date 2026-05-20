import logging
import os

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(level: str | None = None) -> None:
    log_level_name = (level or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=log_level, format=DEFAULT_LOG_FORMAT)
    else:
        root_logger.setLevel(log_level)

    logging.getLogger("app").setLevel(log_level)
