from fastapi import Header, HTTPException
from database import get_db


def verify_api_key(authorization: str = Header(None)) -> dict:
    """
    Dependency — inject into any route that needs auth.
    Usage: project: dict = Depends(verify_api_key)
    Returns the full project row: {id, name, tier, health_score}
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed API key")

    raw_key = authorization.replace("Bearer ", "").strip()
    db = get_db()

    result = (
        db.table("projects")
        .select("id, name, org_id, api_key, tier, created_at")
        .eq("api_key", raw_key)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return result.data