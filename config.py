# src/config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Variables de entorno
HTTP_USER = os.getenv("HTTP_USER")
HTTP_PASSWORD = os.getenv("HTTP_PASSWORD")
DB_TYPE = os.getenv("DB_TYPE")

# Database / Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("DB_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("DB_PASSWORD")

# Backwards-compatibility aliases (scheduled for removal)
DB_URL = SUPABASE_URL
DB_PASSWORD = SUPABASE_KEY
DB_USER = os.getenv("DB_USER")

RCLONE_REMOTE = os.getenv("RCLONE_REMOTE")
RCLONE_CONFIG = os.getenv("RCLONE_CONFIG")

# Configuración adicional
DEFAULT_SIMULTANEOUS_DOWNLOADS = 3
