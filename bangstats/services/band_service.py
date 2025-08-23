from typing import List, Optional, Dict, Any
from bangstats.database.repositories.band_repository import BandRepository
from bangstats.database.models.band import Band
from loguru import logger

class BandService:
    def __init__(self):
        self._repo = BandRepository()
        logger.debug("BandService initialized with BandRepository")

    def get_band_by_id(self, band_id: int) -> Optional[Band]:
        if not isinstance(band_id, int) or band_id <= 0:
            logger.warning(f"Invalid band_id provided: {band_id}")
            return None
        logger.debug(f"Fetching band by id: {band_id}")
        return self._repo.get_by_id(band_id)

    def get_band_by_internal_id(self, internal_band_id: int) -> Optional[Band]:
        if not isinstance(internal_band_id, int) or internal_band_id <= 0:
            logger.warning(f"Invalid internal_band_id provided: {internal_band_id}")
            return None
        logger.debug(f"Fetching band by internal id: {internal_band_id}")
        return self._repo.get_by_internal_id(internal_band_id)

    def get_all_bands(self) -> List[Band]:
        logger.debug("Fetching all bands from database")
        return self._repo.get_all()

    def create_band(self, band_data: Dict[str, Any]) -> Band:
        logger.debug(f"Attempting to create band with data: {band_data}")
        required = ["internal_band_id", "name"]
        for f in required:
            if f not in band_data:
                raise ValueError(f"Missing required field: {f}")
        if self.get_band_by_internal_id(band_data["internal_band_id"]):
            raise ValueError(f"Band with internal_band_id {band_data['internal_band_id']} exists")
        if not isinstance(band_data["internal_band_id"], int) or band_data["internal_band_id"] <= 0:
            raise ValueError("internal_band_id must be a positive integer")
        if not isinstance(band_data["name"], dict):
            raise ValueError("name must be a dict with language keys")
        band, err = self._repo.create(band_data)
        if err:
            raise ValueError(err)
        logger.debug(f"Band created successfully: {band}")
        return band

    def update_band(self, band_id: int, band_data: Dict[str, Any]) -> Band:
        logger.debug(f"Attempting to update band {band_id} with data: {band_data}")
        if not isinstance(band_id, int) or band_id <= 0:
            raise ValueError("Invalid band ID")
        if "internal_band_id" in band_data:
            if not isinstance(band_data["internal_band_id"], int) or band_data["internal_band_id"] <= 0:
                raise ValueError("internal_band_id must be a positive integer")
        if "name" in band_data and not isinstance(band_data["name"], dict):
            raise ValueError("name must be a dict with language keys")
        band, err = self._repo.update(band_id, band_data)
        if err:
            raise ValueError(err)
        logger.debug(f"Band {band_id} updated successfully")
        return band

    def delete_band(self, band_id: int) -> bool:
        logger.debug(f"Attempting to delete band {band_id}")
        if not isinstance(band_id, int) or band_id <= 0:
            raise ValueError("Invalid band ID")
        success, err = self._repo.delete(band_id)
        if not success:
            raise ValueError(err)
        logger.debug(f"Band {band_id} deleted successfully")
        return True

    def search_bands_by_name(self, name_query: str, language: str = "en") -> List[Band]:
        if not name_query or not isinstance(name_query, str):
            logger.warning("Invalid name_query for search_bands_by_name")
            return []
        if not language or not isinstance(language, str):
            logger.warning("Invalid language for search_bands_by_name, defaulting to 'en'")
            language = "en"
        logger.debug(f"Searching bands by name '{name_query.strip()}' in language '{language}'")
        return self._repo.search_by_name(name_query.strip(), language)
