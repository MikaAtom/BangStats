from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from bangstats_server.core.adapters.bestdori import RemoteDataService
from bangstats_server.core.adapters.fake_remote import FakeRemoteDataService
from bangstats_server.core.config import REMOTE_DATA_PROVIDER
from bangstats_server.core.scripts.band_data_organize import band_data_organize
from bangstats_server.core.scripts.event_data_organize import event_data_organize
from bangstats_server.core.scripts.song_data_organize import song_data_organize
from bangstats_server.core.services.band import BandService
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.song import SongService


def get_db_counts() -> tuple[int, int, int]:
    song_service = SongService()
    event_service = EventService()
    band_service = BandService()
    return (
        len(song_service.get_all_songs()),
        len(event_service.get_all_events()),
        len(band_service.get_all_bands()),
    )


def update_db(server: str) -> tuple[int, int, int]:
    song_service = SongService()
    event_service = EventService()
    band_service = BandService()

    def _localized_name(value, locale, fallback="Unknown"):
        if isinstance(value, dict):
            return value.get(locale) or fallback
        return fallback

    if REMOTE_DATA_PROVIDER == "fake":
        remote_data_service = FakeRemoteDataService(server=server)
    else:
        remote_data_service = RemoteDataService(server=server)

    use_organized_payloads = getattr(remote_data_service, "returns_organized_payloads", False)

    songs_in_database = song_service.get_all_songs()
    print("Fetching songs from Bestdori...")
    songs_in_remote = remote_data_service.get_songs_ids()

    logger.info(f"Database initialized with {len(songs_in_database)} songs.")
    logger.info(f"Remote songs fetched: {len(songs_in_remote)} song IDs.")

    songs_in_database_ids = [song.internal_song_id for song in songs_in_database]

    missing_songs = sorted(set(songs_in_remote) - set(songs_in_database_ids))

    if len(missing_songs) > 0:
        total_songs = len(missing_songs)
        print(f"\n--- Updating songs ({total_songs} new) ---")
        logger.info("Mismatch between remote and local song IDs. Updating database...")

        songs_data_by_id = {}
        print("Fetching song details...")
        fetched_count = 0
        max_workers = min(8, total_songs)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_song_id = {
                executor.submit(remote_data_service.get_song_info, song_id): song_id
                for song_id in missing_songs
            }

            for future in as_completed(future_to_song_id):
                song_id = future_to_song_id[future]
                fetched_count += 1
                try:
                    song_data = future.result()
                    if song_data:
                        songs_data_by_id[song_id] = song_data
                except Exception as exc:
                    logger.error(f"Error fetching song {song_id}: {exc}")

                print(f"Fetching song details... ({fetched_count}/{total_songs})")

        for index, song_id in enumerate(missing_songs, start=1):
            song_data = songs_data_by_id.get(song_id)
            if not song_data:
                logger.warning(f"Skipping song {song_id}: no data received")
                continue

            organized_data = song_data if use_organized_payloads else song_data_organize(song_data)
            created_song = song_service.create_song(organized_data)
            song_name = _localized_name(created_song.name, server)

            print(f"Updating song: {song_name} ({index}/{total_songs})")

            logger.info(
                f"Created song: {created_song.internal_song_id} - {song_name}"
            )
    else:
        print("\n--- Songs are up to date ---")

    events_in_database = event_service.get_all_events()
    print("Fetching events from Bestdori...")
    events_in_remote = remote_data_service.get_events_info()

    event_in_database_ids = [event.event_id for event in events_in_database]
    events_in_remote_ids = [int(event_id) for event_id in events_in_remote.keys()]

    logger.info(f"Database initialized with {len(events_in_database)} events.")
    logger.info(f"Remote events fetched: {len(events_in_remote)} event IDs.")

    missing_events = sorted(set(events_in_remote_ids) - set(event_in_database_ids))
    if len(missing_events) > 0:
        total_events = len(missing_events)
        print(f"\n--- Updating events ({total_events} new) ---")
        logger.info("Mismatch between remote and local event IDs. Updating database...")

        for index, event_id in enumerate(missing_events, start=1):
            event_data = events_in_remote.get(str(event_id))

            if event_data:
                organized_event_data = (
                    event_data if use_organized_payloads else event_data_organize(event_id, event_data)
                )
                created_event = event_service.create_event(organized_event_data)
                event_name = _localized_name(created_event.event_name, server)

                print(f"Updating event: {event_name} ({index}/{total_events})")

                logger.info(
                    f"Created event: {created_event.event_id} - {event_name}"
                )
    else:
        print("\n--- Events are up to date ---")

    bands_in_database = band_service.get_all_bands()
    print("Fetching bands from Bestdori...")
    bands_in_remote = remote_data_service.get_bands_info()

    bands_in_database_ids = [band.internal_band_id for band in bands_in_database]
    bands_in_remote_ids = [int(band_id) for band_id in bands_in_remote.keys()]

    logger.info(f"Database initialized with {len(bands_in_database)} bands.")
    logger.info(f"Remote bands fetched: {len(bands_in_remote)} band IDs.")

    missing_bands = sorted(set(bands_in_remote_ids) - set(bands_in_database_ids))
    if len(missing_bands) > 0:
        total_bands = len(missing_bands)
        print(f"\n--- Updating bands ({total_bands} new) ---")
        logger.info("Mismatch between remote and local band IDs. Updating database...")

        for index, band_id in enumerate(missing_bands, start=1):
            band_data = bands_in_remote.get(str(band_id))

            if band_data:
                organized_band_data = (
                    band_data if use_organized_payloads else band_data_organize(band_id, band_data)
                )

                created_band = band_service.create_band(organized_band_data)
                band_name = _localized_name(created_band.name, server)
                print(f"Updating band: {band_name} ({index}/{total_bands})")
                logger.info(
                    f"Created band: {created_band.internal_band_id} - {band_name}"
                )
    else:
        print("\n--- Bands are up to date ---")

    songs_in_database = len(song_service.get_all_songs())
    events_in_database = len(event_service.get_all_events())
    bands_in_database = len(band_service.get_all_bands())

    return songs_in_database, events_in_database, bands_in_database


__all__ = ["get_db_counts", "update_db"]
