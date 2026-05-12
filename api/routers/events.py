from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List

from auth import verify_api_key
from database import get_db
from utils import estimate_cost, redact_pii

router = APIRouter()


class EventPayload(BaseModel):
    session_id: str
    user_message: str
    agent_response: str
    status: str                          # "success" | "failed" | "incomplete"
    latency_ms: int
    model: Optional[str] = "openai/gpt-oss-20b:free"
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    tools_used: Optional[List[str]] = []
    user_id: Optional[str] = None


@router.post("/track")
async def track_event(
    payload: EventPayload,
    project: dict = Depends(verify_api_key),
):
    db = get_db()
    project_id = project["id"]
    cost = estimate_cost(payload.model, payload.input_tokens, payload.output_tokens)

    clean_user_msg  = redact_pii(payload.user_message)
    clean_agent_msg = redact_pii(payload.agent_response)

    # Check if session already exists
    existing = (
        db.table("sessions")
        .select("id, message_count, cost_usd")
        .eq("id", payload.session_id)
        .execute()
    )

    if existing.data:
        # Update existing session
        prev = existing.data[0]
        db.table("sessions").update({
            "status":        payload.status,
            "latency_ms":    payload.latency_ms,
            "cost_usd":      float(prev["cost_usd"] or 0) + cost,
            "message_count": int(prev["message_count"] or 0) + 1,
        }).eq("id", payload.session_id).execute()
    else:
        # Create new session
        db.table("sessions").insert({
            "id":          payload.session_id,
            "project_id":  project_id,
            "user_id":     payload.user_id,
            "status":      payload.status,
            "latency_ms":  payload.latency_ms,
            "cost_usd":    cost,
            "message_count": 1,
        }).execute()

    # Always insert the event record
    db.table("events").insert({
        "session_id":     payload.session_id,
        "type":           "llm_call",
        "user_message":   clean_user_msg[:2000],
        "agent_response": clean_agent_msg[:4000],
        "latency_ms":     payload.latency_ms,
    }).execute()

    return {"status": "ok", "session_id": payload.session_id}


@router.post("/track/webhook")
async def track_webhook(payload: EventPayload):
    """No auth — for n8n / Make / Zapier integrations."""
    db = get_db()
    db.table("events").insert({
        "session_id":     payload.session_id,
        "type":           "webhook",
        "user_message":   redact_pii(payload.user_message)[:2000],
        "agent_response": redact_pii(payload.agent_response)[:4000],
        "latency_ms":     payload.latency_ms,
    }).execute()
    return {"status": "ok"}