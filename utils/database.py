from supabase import create_client
from config import DB_TYPE, DB_URL, DB_PASSWORD

def initialize_client():
    if DB_TYPE == "Supabase":
        url = DB_URL
        key = DB_PASSWORD
        client = create_client(url, key)
        return client
    return None

client = initialize_client()