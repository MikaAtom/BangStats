from typing import List, Optional
from sqlmodel import select
from bangstats_server.core.db.models.band import Band
from bangstats_server.core.db.repositories.base import BaseRepository


class BandRepository(BaseRepository[Band]):
    model = Band

    def get_by_internal_id(self, internal_band_id: int) -> Optional[Band]:
        """Retrieve a band by its internal_band_id."""
        if not isinstance(internal_band_id, int) or internal_band_id <= 0:
            return None

        statement = select(Band).where(Band.internal_band_id == internal_band_id)
        return self._session.exec(statement).first()

    def update(self, band_id: int, band_data: dict) -> tuple[Optional[Band], Optional[str]]:
        """
        Update an existing band record.
        Always returns (band, None) or (None, error_message)
        """
        band = self.get_by_id(band_id)
        if not band:
            return None, f"Band with ID {band_id} not found"

        # If updating internal_band_id, check it doesn't conflict
        if "internal_band_id" in band_data and band_data["internal_band_id"] != band.internal_band_id:
            existing = self.get_by_internal_id(band_data["internal_band_id"])
            if existing and existing.id != band_id:
                return None, f"Band with internal_band_id {band_data['internal_band_id']} already exists"

        return super().update(band_id, band_data, f"Band with ID {band_id} not found")

    def delete(self, band_id: int) -> tuple[bool, Optional[str]]:
        """
        Delete a band by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        return super().delete(band_id, f"Band with ID {band_id} not found")

    def search_by_name(self, name_query: str, language: str = "en") -> List[Band]:
        """Search for bands by name (partial match in specified language)."""
        if not name_query or not isinstance(name_query, str):
            return []

        try:
            statement = select(Band).where(Band.name[language].contains(name_query))
            return self._session.exec(statement).all()
        except Exception:
            return []

    def list_since_id(self, since_id: int, limit: int = 5000) -> List[Band]:
        if not isinstance(since_id, int) or since_id < 0:
            return []
        statement = (
            select(Band)
            .where(Band.id > since_id)
            .order_by(Band.id)
            .limit(limit)
        )
        return self._session.exec(statement).all()