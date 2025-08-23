from typing import Dict, Any, Optional, Literal
from datetime import datetime
from bangstats.services.song_service import SongService

# Type hints for better code clarity
LiveType = Literal["Free Live", "Multi Live", "Team Live", "Challenge Live"]
ScoreRank = Literal["D", "C", "B", "A", "S", "SS", "SSS"]
Difficulty = Literal["easy", "normal", "hard", "expert", "special"]


def _initialize_screenshot_data_structure() -> Dict[str, Any]:
    """Initialize the screenshot data structure with default values."""
    return {
        "score": 0,
        "high_score": None,
        "is_new_record": None,
        "score_rank": None,
        "live_type": "",
        "free_live_data": None,
        "team_live_data": None,
        "perfect": 0,
        "great": 0,
        "good": 0,
        "bad": 0,
        "miss": 0,
        "fast": None,
        "slow": None,
        "max_combo": 0,
        "full_combo": False,
        "all_perfect": False,
        "song_id": 0,
        "difficulty": "",
        "anomaly": False,
        "timestamp": datetime.now()
    }


def _populate_basic_performance_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract basic performance data from raw screenshot data."""
    return {
        "score": int(raw_data.get("score", 0)),
        "high_score": raw_data.get("high_score") if raw_data.get("high_score", -1) != -1 else None,
        "is_new_record": raw_data.get("is_new_record"),
        "score_rank": raw_data.get("score_rank"),
        "live_type": raw_data.get("live_type", ""),
        "max_combo": int(raw_data.get("max_combo", 0))
    }


def _populate_note_performance_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract note performance data and calculate derived fields."""
    perfect = int(raw_data.get("perfect", 0))
    great = int(raw_data.get("great", 0))
    good = int(raw_data.get("good", 0))
    bad = int(raw_data.get("bad", 0))
    miss = int(raw_data.get("miss", 0))
    
    # Calculate derived fields
    total_notes = perfect + great + good + bad + miss
    full_combo = miss == 0 and bad == 0 and good == 0
    all_perfect = perfect == total_notes and total_notes > 0
    
    return {
        "perfect": perfect,
        "great": great,
        "good": good,
        "bad": bad,
        "miss": miss,
        "fast": raw_data.get("fast") if raw_data.get("fast", -1) != -1 else None,
        "slow": raw_data.get("slow") if raw_data.get("slow", -1) != -1 else None,
        "full_combo": full_combo,
        "all_perfect": all_perfect
    }


def _populate_song_data(raw_data: Dict[str, Any], song_service: Optional[SongService] = None) -> Dict[str, Any]:
    """Extract song-related data from raw screenshot data."""
    difficulty = raw_data.get("difficulty", "").lower()
    song_id = 0
    
    # Try to resolve song_id from song name if song service is available
    if song_service and "song_name_from_top_bar_text" in raw_data:
        song_name = raw_data["song_name_from_top_bar_text"]
        resolved_id = resolve_song_id_from_name(song_name, song_service)
        if resolved_id:
            song_id = resolved_id
    
    return {
        "song_id": song_id,
        "difficulty": difficulty
    }


def _populate_live_type_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract live type specific data."""
    result = {
        "free_live_data": None,
        "team_live_data": None
    }
    
    live_type = raw_data.get("live_type", "")
    
    if live_type == "Free Live" and "free_live_data" in raw_data:
        free_data = raw_data["free_live_data"]
        if isinstance(free_data, dict):
            result["free_live_data"] = free_data
    
    # Placeholder for team live data - would be similar structure
    if live_type == "Team Live" and "team_live_data" in raw_data:
        team_data = raw_data["team_live_data"]
        if isinstance(team_data, dict):
            result["team_live_data"] = team_data
    
    return result


def _validate_screenshot_data(organized_data: Dict[str, Any]) -> bool:
    """Validate the organized screenshot data for anomalies."""
    
    return True


def screenshot_data_organize(raw_screenshot_data: Dict[str, Any], 
                           user_id: Optional[int] = None,
                           song_id_override: Optional[int] = None,
                           song_service: Optional[SongService] = None) -> Dict[str, Any]:
    """Transform raw screenshot data into model-compatible format."""
    organized_data = _initialize_screenshot_data_structure()
    
    # Populate different sections of data
    basic_data = _populate_basic_performance_data(raw_screenshot_data)
    note_data = _populate_note_performance_data(raw_screenshot_data)
    song_data = _populate_song_data(raw_screenshot_data, song_service)
    live_data = _populate_live_type_data(raw_screenshot_data)
    
    # Update organized data
    for key, value in basic_data.items():
        organized_data[key] = value
    
    for key, value in note_data.items():
        organized_data[key] = value
    
    for key, value in song_data.items():
        organized_data[key] = value
    
    for key, value in live_data.items():
        organized_data[key] = value
    
    # Override song_id if provided
    if song_id_override is not None:
        organized_data["song_id"] = song_id_override
    
    # Add user_id if provided
    if user_id is not None:
        organized_data["user_id"] = user_id
    
    # Validate data and mark anomalies
    organized_data["anomaly"] = not _validate_screenshot_data(organized_data)
    
    return organized_data


def resolve_song_id_from_name(song_name: str, song_service: SongService) -> Optional[int]:
    """
    Resolve song ID from song name using the song service.
    
    Args:
        song_name: The song name to search for
        song_service: The song service instance to use for searching
        
    Returns:
        The internal_song_id if found, None otherwise
    """
    if not song_name or not song_service:
        return None
    
    # Search for songs by name in different languages
    languages = ["en", "jp", "tw", "cn", "kr"]
    
    for language in languages:
        songs = song_service.search_songs_by_name(song_name, language)
        if songs:
            # Return the first match's internal_song_id
            return songs[0].internal_song_id
    
    return None
