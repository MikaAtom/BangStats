import os


DEFAULT_SERVER_URL = (
    os.getenv("BANGSTATS_SERVER_URL", "http://localhost:8000").strip()
    or "http://localhost:8000"
)
