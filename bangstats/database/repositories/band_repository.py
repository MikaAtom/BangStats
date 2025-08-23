from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select
from bangstats.database.models.band import Band
from bangstats.database.db import get_session


class BandRepository:
    def __init__(self):
        # initialize one session to reuse
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        # close the session generator (triggers cleanup)
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_by_id(self, band_id: int) -> Optional[Band]:
        """Retrieve a band by its primary key ID."""
        if not isinstance(band_id, int) or band_id <= 0:
            return None
        return self._session.get(Band, band_id)

    def get_by_internal_id(self, internal_band_id: int) -> Optional[Band]:
        """Retrieve a band by its internal_band_id."""
        if not isinstance(internal_band_id, int) or internal_band_id <= 0:
            return None

        statement = select(Band).where(Band.internal_band_id == internal_band_id)
        return self._session.exec(statement).first()

    def get_all(self) -> List[Band]:
        """Retrieve all bands from the database."""
        statement = select(Band)
        return self._session.exec(statement).all()

    def create(self, band_data: Dict[str, Any]) -> Tuple[Optional[Band], Optional[str]]:
        """
        Create a new band record.
        Always returns (band, None) or (None, error_message)
        """

        try:
            band = Band(**band_data)
            self._session.add(band)
            self._session.commit()
            self._session.refresh(band)
            return band, None
        except Exception as e:
            return None, f"Database error: {str(e)}"

    def update(self, band_id: int, band_data: Dict[str, Any]) -> Tuple[Optional[Band], Optional[str]]:
        """
        Update an existing band record.
        Always returns (band, None) or (None, error_message)
        """
        band = self._session.get(Band, band_id)
        if not band:
            return None, f"Band with ID {band_id} not found"

        # If updating internal_band_id, check it doesn't conflict
        if "internal_band_id" in band_data and band_data["internal_band_id"] != band.internal_band_id:
            existing = self.get_by_internal_id(band_data["internal_band_id"])
            if existing and existing.id != band_id:
                return None, f"Band with internal_band_id {band_data['internal_band_id']} already exists"

        try:
            # Apply updates
            for key, value in band_data.items():
                setattr(band, key, value)

            self._session.add(band)
            self._session.commit()
            self._session.refresh(band)
            return band, None
        except Exception as e:
            self._session.rollback()
            return None, f"Database error: {str(e)}"

    def delete(self, band_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete a band by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        band = self._session.get(Band, band_id)
        if not band:
            return False, f"Band with ID {band_id} not found"

        try:
            self._session.delete(band)
            self._session.commit()
            return True, None
        except Exception as e:
            self._session.rollback()
            return False, f"Database error: {str(e)}"

    def search_by_name(self, name_query: str, language: str = "en") -> List[Band]:
        """Search for bands by name (partial match in specified language)."""
        if not name_query or not isinstance(name_query, str):
            return []

        try:
            statement = select(Band).where(Band.name[language].contains(name_query))
            return self._session.exec(statement).all()
        except Exception:
            return []