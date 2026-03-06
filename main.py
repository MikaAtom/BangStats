# Load .env before any other bangstats imports so env vars are available everywhere
from dotenv import load_dotenv

load_dotenv()

from bangstats.cli.app import run

run()
