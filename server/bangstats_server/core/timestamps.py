import datetime
import re
from typing import Optional

from loguru import logger


def extract_timestamp_from_filename(filename: str) -> Optional[int]:
    """Extract milliseconds timestamp from known screenshot filename patterns."""
    unix_ms_match = re.search(r"Screenshot_(\d{13})(?:\D|$)", filename)
    if unix_ms_match:
        return int(unix_ms_match.group(1))

    compact_match = re.search(r"Screenshot_(\d{8})[-_](\d{6})", filename)
    if compact_match:
        dt = datetime.datetime.strptime(
            compact_match.group(1) + compact_match.group(2),
            "%Y%m%d%H%M%S",
        )
        return int(dt.timestamp() * 1000)

    dashed_match = re.search(r"(\d{4})-(\d{2})-(\d{2})[-_](\d{2})-(\d{2})-(\d{2})", filename)
    if dashed_match:
        year, month, day, hour, minute, second = dashed_match.groups()
        dt = datetime.datetime.strptime(
            f"{year}{month}{day}{hour}{minute}{second}",
            "%Y%m%d%H%M%S",
        )
        return int(dt.timestamp() * 1000)

    logger.warning(f"Could not extract timestamp from filename: {filename}")
    return None
