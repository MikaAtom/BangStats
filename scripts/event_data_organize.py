from typing import Dict, Any, List, Literal

Language = Literal["jp", "en", "tw", "cn", "kr"]
LANGUAGES: List[Language] = ["jp", "en", "tw", "cn", "kr"]


def event_data_organize(event_id: int, raw_event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw Bestdori event data into model-compatible format.
    """
    # If event_id is not provided, try to extract from raw_event_data
    if event_id is None:
        raise ValueError("Event ID must be provided.")

    # Map eventName, startAt, endAt to language keys
    def map_lang_field(field: List[Any]) -> Dict[Language, Any]:
        return {
            lang: field[i] if i < len(field) else None
            for i, lang in enumerate(LANGUAGES)
        }

    event_name = map_lang_field(raw_event_data.get("eventName", [None] * 5))
    event_start_at = map_lang_field(raw_event_data.get("startAt", [None] * 5))
    event_end_at = map_lang_field(raw_event_data.get("endAt", [None] * 5))

    # Get attribute (first in attributes list, if present)
    attribute = None
    attributes = raw_event_data.get("attributes", [])
    if attributes and isinstance(attributes, list) and len(attributes) > 0:
        attribute = attributes[0].get("attribute")

    # Get characters (list of characterId)
    characters = []
    for char in raw_event_data.get("characters", []):
        if "characterId" in char:
            characters.append(char["characterId"])

    # Compose misc
    misc = {
        "asset_bundle_name": raw_event_data.get("assetBundleName"),
        "banner_asset_bundle_name": raw_event_data.get("bannerAssetBundleName"),
        "atribute": attribute,
        "characters": characters,
    }

    return {
        "event_id": event_id,
        "event_type": raw_event_data.get("eventType"),
        "event_name": event_name,
        "event_start_at": event_start_at,
        "event_end_at": event_end_at,
        "misc": misc,
    }
