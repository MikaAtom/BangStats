from loguru import logger
from datetime import datetime
import os

from bangstats_server.core.config import LOGS_DIR, LOG_LEVEL, LOG_FILE_NAME

INFO_FORMAT = "[<green>{time:YYYY-MM-DD HH:mm:ss}</green>][<level>{level: <4}</level>]: {message}"
DEBUG_FORMAT = "[{time:YYYY-MM-DD HH:mm:ss.SSS}][{level: <4}][{file}:{function}:{line}]: {message}"

def setup_loguru(
    rotation="10 MB",
    retention="10 days",
    compression="zip"
):
    log_dir = LOGS_DIR
    level = LOG_LEVEL
    log_file_name = LOG_FILE_NAME


    # Select format
    if level == "debug":
        fmt = DEBUG_FORMAT
    else:
        fmt = INFO_FORMAT

    # Generate log filename by creation time
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_file_name.format(timestamp=timestamp)
    log_file = os.path.join(log_dir, log_file)

    # Remove default handlers
    logger.remove()
    # Add stdout handler
    # logger.add(sys.stdout, level=level, format=fmt, enqueue=True)
    # Always add file handler
    logger.add(
        log_file,
        level="DEBUG",
        format=DEBUG_FORMAT,
        rotation=rotation,
        retention=retention,
        compression=compression,
        enqueue=True
    )

# Run setup on import
setup_loguru()
