from typing import Dict, Any, List, Literal

Language = Literal["jp", "en", "tw", "cn", "kr"]
LANGUAGES: List[Language] = ["jp", "en", "tw", "cn", "kr"]


def band_data_organize(band_id: int, raw_band_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw Bestdori event data into model-compatible format.
    """

    return {
        "internal_band_id": band_id,
        "name": {lang: raw_band_data["bandName"][i] for i, lang in enumerate(LANGUAGES)}
    }
