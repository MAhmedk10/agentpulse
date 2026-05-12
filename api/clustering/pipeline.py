import os
import json
import httpx
from datetime import datetime, timedelta, timezone, date

from database import get_db

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
GEMINI_MODEL   = "openai/gpt-oss-20b:free"


async def call_gemini(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://agentpulse.io",
            },
            json={
                "model": GEMINI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
            },
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def run_clustering_for_project(project_id: str) -> list:
    db = get_db()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Fix 1: sessions uses started_at not created_at
    sessions = (
        db.table("sessions")
        .select("id")
        .eq("project_id", project_id)
        .gte("started_at", week_ago)        # ← fixed
        .execute()
    )

    if not sessions.data or len(sessions.data) < 2:
        return []   # lowered threshold to 2 for easier testing

    session_ids = [s["id"] for s in sessions.data]

    events = (
        db.table("events")
        .select("user_message")
        .in_("session_id", session_ids[:200])
        .not_.is_("user_message", "null")
        .execute()
    )

    messages = [e["user_message"] for e in events.data if e.get("user_message")]
    if len(messages) < 2:
        return []

    msg_list = "\n".join(f"- {m[:120]}" for m in messages[:80])

    prompt = f"""You are analyzing questions that users sent to an AI assistant.
Group these questions into topic clusters.
Return ONLY valid JSON — no markdown fences, no explanation.

Questions:
{msg_list}

Return exactly this JSON structure (2 to 6 clusters):
{{
  "clusters": [
    {{"label": "Topic name in 3-5 words", "count": 12}},
    {{"label": "Another topic", "count": 8}}
  ]
}}

Rules:
- label must be 3-5 words describing the topic
- count is the approximate number of questions in that cluster"""

    raw = ""
    try:
        raw     = await call_gemini(prompt)
        print(f"[clustering] raw response: {raw[:500]}")
        # Strip markdown fences if model adds them
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed   = json.loads(cleaned.strip())
        clusters = parsed.get("clusters", [])
    except Exception as e:
        print(f"[clustering] parse error: {e} | raw: {raw[:300]}")
        return []

    # Fix 2: removed trend column — not in schema
    today = date.today().isoformat()
    for cluster in clusters:
        db.table("intent_clusters").upsert(
            {
                "project_id":    project_id,
                "label":         cluster["label"],
                "session_count": cluster.get("count", 0),
                "week":          today,
            },
            on_conflict="project_id,label,week",   # Fix 3: needs unique constraint above
        ).execute()

    return clusters