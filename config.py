# src/config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Variables de entorno
HTTP_USER = os.getenv("HTTP_USER")
HTTP_PASSWORD = os.getenv("HTTP_PASSWORD")
DB_TYPE = os.getenv("DB_TYPE")
DB_URL = os.getenv("DB_URL")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
RCLONE_REMOTE = os.getenv("RCLONE_REMOTE")
RCLONE_CONFIG = os.getenv("RCLONE_CONFIG")

# Configuración adicional
DEFAULT_SIMULTANEOUS_DOWNLOADS = 3
