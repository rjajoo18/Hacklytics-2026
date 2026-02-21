"""
Centralised configuration.

Env-var lookup order (first non-empty value wins):

  SUPABASE_URL
  NEXT_PUBLIC_SUPABASE_URL        ← the name already used by the Next.js frontend

  SUPABASE_SERVICE_ROLE_KEY       ← preferred for server-side (bypasses RLS)
  SUPABASE_ANON_KEY
  NEXT_PUBLIC_SUPABASE_ANON_KEY   ← fallback to frontend key

Both .env.local and .env are loaded from the project root so the same
credentials file the frontend uses works here too.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Walk up from this file (backend/app/core/) until we find the env files.
_core_dir = Path(__file__).resolve().parent          # backend/app/core
_project_root = _core_dir.parent.parent.parent       # Hacklytics_2026/

for _env_name in (".env.local", ".env"):
    _env_path = _project_root / _env_name
    if _env_path.exists():
        load_dotenv(_env_path, override=False)


def get_supabase_url() -> str:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
    if not url:
        raise RuntimeError(
            "Supabase URL not found. "
            "Set SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) in .env or .env.local."
        )
    return url


def get_supabase_key() -> str:
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    )
    if not key:
        raise RuntimeError(
            "Supabase key not found. "
            "Set SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY, "
            "or NEXT_PUBLIC_SUPABASE_ANON_KEY in .env or .env.local."
        )
    return key
