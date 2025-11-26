import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NASA_FIRMS_MAP_KEY = os.getenv("NASA_FIRMS_MAP_KEY")

SEATTLE_FIRE_BASE_URL = os.getenv("SEATTLE_FIRE_BASE_URL")
SEATTLE_POLICE_BASE_URL = os.getenv("SEATTLE_POLICE_BASE_URL")