from typing import Union

from bangstats_server.core.db.models.event import Event


def parse_event_timestamp_ms(
    value: Union[int, float, str, dict, None],
    *,
    language: str = "en",
) -> int | None:
    if isinstance(value, dict):
        value = value.get(language)
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            value = int(stripped)
        except ValueError:
            return None
    elif isinstance(value, float):
        value = int(value)
    elif not isinstance(value, int):
        return None

    if value <= 0:
        return None
    if value < 10_000_000_000:
        return value * 1000
    return value


def get_event_window_ms(event: Event, *, language: str = "en") -> tuple[int | None, int | None]:
    start = parse_event_timestamp_ms(getattr(event, "event_start_at", None), language=language)
    end = parse_event_timestamp_ms(getattr(event, "event_end_at", None), language=language)
    return start, end


def event_is_active(event: Event, *, timestamp_ms: int, language: str = "en") -> bool:
    start, end = get_event_window_ms(event, language=language)
    return start is not None and end is not None and start <= timestamp_ms <= end
