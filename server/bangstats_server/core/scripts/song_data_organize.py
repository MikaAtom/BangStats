from typing import Dict, Any, List, Literal

# Add more specific type hints
Language = Literal["jp", "en", "tw", "cn", "kr"]
Difficulty = Literal["easy", "normal", "hard", "expert", "special"]

# At the top of the file
LANGUAGES: List[Language] = ["jp", "en", "tw", "cn", "kr"]
DIFFICULTIES: List[Difficulty] = ["easy", "normal", "hard", "expert", "special"]


def _initialize_song_data_structure() -> Dict[str, Any]:
    """Initialize the song data structure with default values."""
    return {
        "internal_song_id": 0,
        "tag": "",
        "name": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "band_id": 0,
        "lyricist": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "composer": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "arranger": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "levels": {
            "easy": "",
            "normal": "",
            "hard": "",
            "expert": "",
            "special": "",
        },
        "note_counts": {
            "easy": "",
            "normal": "",
            "hard": "",
            "expert": "",
            "special": "",
        },
        "bpm": 0.0,
        "length": 0.0,
        "published_at": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "closed_at": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        "special": {
            "available": False,
            "published_at": {"jp": "", "en": "", "tw": "", "cn": "", "kr": ""},
        },
    }


def _populate_basic_information(song_id: int, raw_song_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return the basic song information."""
    return {
        "internal_song_id": song_id,
        "band_id": int(raw_song_data["bandId"]),
        "tag": raw_song_data["tag"],
        "length": float(raw_song_data["length"]),
        "bpm": float(raw_song_data["bpm"]["0"][0]["bpm"]),
    }


def _populate_language_fields(raw_song_data: Dict[str, Any]) -> Dict[str, Dict[Language, str]]:
    """Return all language-specific fields."""
    result = {
        "name": {},
        "lyricist": {},
        "composer": {},
        "arranger": {},
        "published_at": {},
        "closed_at": {},
    }

    for language in LANGUAGES:
        result["name"][language] = raw_song_data["musicTitle"][LANGUAGES.index(language)]
        result["lyricist"][language] = raw_song_data["lyricist"][LANGUAGES.index(language)]
        result["composer"][language] = raw_song_data["composer"][LANGUAGES.index(language)]
        result["arranger"][language] = raw_song_data["arranger"][LANGUAGES.index(language)]

        result["published_at"][language] = raw_song_data["publishedAt"][
            LANGUAGES.index(language)
        ]
        result["closed_at"][language] = raw_song_data["closedAt"][LANGUAGES.index(language)]

    return result


def _populate_difficulty_information(raw_song_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return difficulties, note counts and special difficulty information."""
    result = {"levels": {}, "note_counts": {}, "special": {"available": False, "published_at": {}}}

    for i, _ in enumerate(raw_song_data["difficulty"]):
        str_i = str(i)

        result["levels"][DIFFICULTIES[i]] = raw_song_data["difficulty"][str_i]["playLevel"]
        result["note_counts"][DIFFICULTIES[i]] = raw_song_data["notes"][str_i]

        # Check if special is available
        if i == 4:
            result["special"]["available"] = True
            for language in LANGUAGES:
                try:
                    special_published_at = raw_song_data["difficulty"][str_i]["publishedAt"][
                        LANGUAGES.index(language)
                    ]
                except (IndexError, KeyError):
                    special_published_at = raw_song_data["publishedAt"][LANGUAGES.index(language)]

                result["special"]["published_at"][language] = special_published_at

    return result


def song_data_organize(raw_song_data: Dict[str, Any], song_id: int = None) -> Dict[str, Any]:
    """Transform raw Bestdori song data into model-compatible format."""
    organized_song_data = _initialize_song_data_structure()

    if song_id is None:
        # If no song_id is provided, try to extract it from the raw data
        if "bgmId" in raw_song_data:
            song_id = int(raw_song_data["bgmId"].replace("bgm", ""))
        else:
            raise ValueError("Song ID must be provided or found in raw data.")

    basic_information = _populate_basic_information(song_id, raw_song_data)
    language_fields = _populate_language_fields(raw_song_data)
    difficulty_information = _populate_difficulty_information(raw_song_data)

    # Update the organized data with the returned information
    for key, value in basic_information.items():
        organized_song_data[key] = value

    for key, value in language_fields.items():
        organized_song_data[key] = value

    for key, value in difficulty_information.items():
        organized_song_data[key] = value

    return organized_song_data
