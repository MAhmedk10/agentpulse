import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_PROJECT_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
)

def get_db() -> Client:
    return supabase