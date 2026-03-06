import json
import os
import requests
import time
from typing import Dict, List, Any, Optional, Callable
from loguru import logger

from bangstats_server.core.config import (
    REMOTE_CACHE,
    REMOTE_REQUEST_RETRIES,
    REMOTE_REQUEST_TIMEOUT,
    SERVERS,
)


class RemoteDataService:
    """Service for fetching and caching remote data from Bestdori API."""

    # API endpoints
    BASE_API_URL = "https://bestdori.com/api"
    SONGS_ALL_API = BASE_API_URL + "/songs/all.5.json"
    SONG_INFO_API = BASE_API_URL + "/songs/{song_id}.json"
    BANDS_API = BASE_API_URL + "/bands/all.1.json"
    EVENTS_API = BASE_API_URL + "/events/all.5.json"

    def __init__(self, server: str = "en"):
        """Initialize the remote data service with configuration."""
        self.cache_folder_path = REMOTE_CACHE
        self.cache_songs_folder_path = self.cache_folder_path / "songs"
        self.session = requests.Session()

        if not os.path.exists(self.cache_folder_path):
            os.makedirs(self.cache_folder_path)

        if not os.path.exists(self.cache_songs_folder_path):
            os.makedirs(self.cache_songs_folder_path)

        self.remote_request_retries = REMOTE_REQUEST_RETRIES
        self.remote_request_timeout = REMOTE_REQUEST_TIMEOUT
        self.server_id = SERVERS.get(server, 1)

    def _with_retry(
        self, func: Callable, retries: int = None, delay: int = None
    ):  # pragma: no cover
        retries = retries if retries is not None else self.remote_request_retries
        delay = delay if delay is not None else self.remote_request_timeout
        """
        Execute a function with retry logic.

        Args:
            func: Function to execute
            retries: Number of retry attempts
            delay: Delay between retries in seconds

        Returns:
            Function result or raises the last exception
        """
        attempts = 0
        last_error = None

        while attempts <= retries:
            try:
                return func()
            except Exception as e:
                last_error = e
                attempts += 1
                if attempts > retries:
                    raise last_error
                time.sleep(delay)

        # Should never reach here, but just in case
        raise last_error if last_error else Exception("Unknown error in retry logic")

    def _get_remote_songs_ids(self) -> List[dict]:
        """Fetch all song IDs from Bestdori API."""

        def fetch():
            logger.debug(f"Requesting all songs from {self.SONGS_ALL_API}")
            response = self.session.get(
                self.SONGS_ALL_API, timeout=self.remote_request_timeout
            )
            logger.debug(
                f"Received response with status {response.status_code} for songs list"
            )
            if response.status_code == 200:
                songs_data = response.json()
                logger.debug(f"Fetched {len(songs_data)} songs from remote API")
                return songs_data
            else:
                raise Exception(
                    f"Failed to fetch songs. Status code: {response.status_code}"
                )

        try:
            return self._with_retry(fetch)
        except Exception as e:
            logger.error(f"All retries failed for fetching songs: {str(e)}")
            return {}

    def _get_remote_song_info(self, song_id: str) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific song from Bestdori API.

        Args:
            song_id: ID of the song to fetch
        """

        def fetch():
            url = self.SONG_INFO_API.format(song_id=song_id)
            logger.debug(f"Requesting song info for {song_id} from {url}")
            response = self.session.get(url, timeout=self.remote_request_timeout)
            logger.debug(
                f"Received response with status {response.status_code} for song {song_id}"
            )
            if response.status_code == 200:
                logger.debug(f"Fetched song info for {song_id} from remote API")
                return response.json()
            else:
                raise Exception(
                    f"Failed to fetch song info. Status code: {response.status_code}"
                )

        return self._with_retry(fetch)

    def _get_remote_bands_info(self) -> Dict[str, Any]:
        """Fetch band information from Bestdori API."""

        def fetch():
            logger.debug(f"Requesting bands info from {self.BANDS_API}")
            response = self.session.get(
                self.BANDS_API, timeout=self.remote_request_timeout
            )
            logger.debug(
                f"Received response with status {response.status_code} for bands info"
            )
            if response.status_code == 200:
                logger.debug("Fetched bands info from remote API")
                return response.json()
            else:
                raise Exception(
                    f"Failed to fetch bands info. Status code: {response.status_code}"
                )

        return self._with_retry(fetch)

    def _get_remote_events_info(self) -> Dict[str, Any]:
        """Fetch event information from Bestdori API."""

        def fetch():
            logger.debug(f"Requesting events info from {self.EVENTS_API}")
            response = self.session.get(
                self.EVENTS_API, timeout=self.remote_request_timeout
            )
            logger.debug(
                f"Received response with status {response.status_code} for events info"
            )
            if response.status_code == 200:
                logger.debug("Fetched events info from remote API")
                return response.json()
            else:
                raise Exception(
                    f"Failed to fetch events info. Status code: {response.status_code}"
                )

        return self._with_retry(fetch)

    def _cache_song_info(self, song_id: str, song_info: Dict[str, Any]) -> bool:
        """Save song information to the local cache."""
        try:
            title = song_info.get("musicTitle")[self.server_id]

            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").rstrip()

            file_name = f"{song_id}_{safe_title}.json"
            file_path = os.path.join(self.cache_songs_folder_path, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(song_info, f, ensure_ascii=False, indent=4)

            logger.info(f"Cached song info for {song_id} at {file_path}")

            return True
        except Exception as e:
            logger.error(f"Error caching song info for {song_id}: {str(e)}")
            return False

    def _cache_bands_info(self, bands_info: Dict[str, Any]) -> bool:
        """Save band information to the local cache."""
        try:
            file_path = os.path.join(self.cache_folder_path, "bands.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(bands_info, f, ensure_ascii=False, indent=4)
            logger.info(f"Cached bands info at {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error caching bands info: {str(e)}")
            return False

    def _cache_events_info(self, events_info: Dict[str, Any]) -> bool:
        """Save event information to the local cache."""
        try:
            file_path = os.path.join(self.cache_folder_path, "events.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(events_info, f, ensure_ascii=False, indent=4)
            logger.info(f"Cached events info at {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error caching events info: {str(e)}")
            return False

    def _get_cache_song_info(self, song_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve song information from the local cache."""
        try:
            matching_files = [
                f
                for f in os.listdir(self.cache_songs_folder_path)
                if f.startswith(f"{song_id}_") and f.endswith(".json")
            ]

            if not matching_files:
                logger.debug(f"No cache found for song {song_id}")
                return None

            file_path = os.path.join(self.cache_songs_folder_path, matching_files[0])
            logger.debug(f"Loading cached song info for {song_id} from {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except (IOError, json.JSONDecodeError, IndexError) as e:
            logger.error(f"Error loading cached song info for {song_id}: {str(e)}")
            return None

    def get_songs_ids(self) -> List[int]:
        """Get all song IDs from API."""
        song_on_server = []

        # Fetch from remote API
        try:
            remote_ids = self._get_remote_songs_ids()
            logger.debug(f"Filtering songs for server {self.server_id}")
            for song_id, song_data in remote_ids.items():
                if not song_data.get("publishedAt")[self.server_id] == None:
                    song_on_server.append(int(song_id))

            logger.info(f"Found {len(song_on_server)} songs for server {self.server_id}")
            return song_on_server
        except Exception as e:
            logger.error(f"Error fetching song IDs: {str(e)}")
            return []

    def get_song_info(
        self, song_id: str, force_remote: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get song info from API.

        Args:
            song_id: ID of the song to fetch
            force_remote: Set to True to bypass cache and fetch fresh data
        """
        if not force_remote:
            cached_info = self._get_cache_song_info(song_id)
            if cached_info:
                logger.info(f"Retrieved cached info for song {song_id}")
                return cached_info
            else:
                logger.debug(f"No cached info for song {song_id}, fetching from remote")

        try:
            remote_info = self._get_remote_song_info(song_id)
            if remote_info:
                self._cache_song_info(song_id, remote_info)
            logger.info(f"Fetched song info for {song_id} from remote API")
            return remote_info
        except Exception as e:
            logger.error(f"Error fetching song {song_id}: {str(e)}")
            return None

    def get_bands_info(self) -> Dict[str, Any]:
        """Get band info from API."""
        bands_on_server = {}

        try:
            remote_info = self._get_remote_bands_info()
            logger.debug(f"Filtering bands for server {self.server_id}")
            if remote_info:
                for band_id, band_data in remote_info.items():
                    if not band_data.get("bandName")[self.server_id] == None:
                        bands_on_server[str(band_id)] = band_data

                self._cache_bands_info(bands_on_server)

            logger.info(f"Found {len(bands_on_server)} bands for server {self.server_id}")
            return bands_on_server
        except Exception as e:
            logger.error(f"Error fetching bands info: {str(e)}")
            return {}

    def get_events_info(self) -> Dict[str, Any]:
        """Get event info from API."""

        events_on_server = {}

        try:
            remote_info = self._get_remote_events_info()
            logger.debug(f"Filtering events for server {self.server_id}")
            if remote_info:
                for event_id, event_data in remote_info.items():
                    if not event_data.get("endAt")[self.server_id] == None:
                        events_on_server[str(event_id)] = event_data

                self._cache_events_info(events_on_server)
            logger.info(f"Found {len(events_on_server)} events for server {self.server_id}")
            return events_on_server
        except Exception as e:
            logger.error(f"Error fetching events info: {str(e)}")
            return {}
