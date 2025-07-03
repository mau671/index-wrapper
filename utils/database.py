from supabase import create_client
from config import DB_TYPE, SUPABASE_URL, SUPABASE_KEY


def initialize_client():
    if DB_TYPE == "Supabase":
        url = SUPABASE_URL
        key = SUPABASE_KEY
        client = create_client(url, key)
        return client
    return None


client = initialize_client()
