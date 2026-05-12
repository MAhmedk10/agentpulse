from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx
import os
from auth import verify_api_key
from database import get_db

router = APIRouter()


class CopilotQuery(BaseModel):
    question: str


@router.post("/projects/{project_id}/copilot")
async def copilot(
    project_id: str,
    body: CopilotQuery,
    project: dict = Depends(verify_api_key),
):
    db = get_db()

    # ── RAG STEP 1: Retrieve data from Supabase ──
    sessions = (
        db.table("sessions")
        .select("id, status, cost_usd, latency_ms, started_at")
        .eq("project_id", project_id)
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )

    total  = len(sessions.data)
    failed = [s for s in sessions.data if s["status"] == "failed"]

    events = (
        db.table("events")
        .select("user_message, agent_response, status, latency_ms")
        .in_("session_id", [s["id"] for s in sessions.data[:20]])
        .execute()
    )

    clusters = (
        db.table("intent_clusters")
        .select("label, session_count")
        .eq("project_id", project_id)
        .order("session_count", desc=True)
        .limit(5)
        .execute()
    )

    # ── RAG STEP 2: Build context from retrieved data ──
    success_rate = round((total - len(failed)) / total * 100, 1) if total else 0
    avg_latency  = round(sum(s["latency_ms"] or 0 for s in sessions.data) / total) if total else 0
    total_cost   = round(sum(float(s["cost_usd"] or 0) for s in sessions.data), 4)

    cluster_text = "\n".join(
        f"  - {c['label']}: {c['session_count']} sessions"
        for c in clusters.data
    ) or "  No clusters generated yet."

    sample_convos = "\n".join(
        f"  - User: {e['user_message'][:100]} | Status: {e['status']} | Latency: {e['latency_ms']}ms"
        for e in events.data[:10]
        if e.get("user_message")
    ) or "  No conversations found."

    context = f"""
Agent Performance Data (last {total} sessions):
- Total sessions: {total}
- Failed sessions: {len(failed)}
- Success rate: {success_rate}%
- Average latency: {avg_latency}ms
- Total cost: ${total_cost}

Top user intent clusters this week:
{cluster_text}

Sample recent conversations:
{sample_convos}
"""

    # ── RAG STEP 3: Send question + context to LLM ──
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://agentpulse.io",
            },
            json={
                "model": "openai/gpt-oss-20b:free",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are AgentPulse Copilot — an AI analyst that helps "
                            "developers understand their AI agent's performance. "
                            "Answer questions using only the data provided. "
                            "Be specific, actionable, and concise. "
                            "Always end with one concrete recommendation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Here is my agent's performance data:\n{context}\n\nMy question: {body.question}",
                    },
                ],
                "max_tokens": 500,
            },
        )
        data = response.json()

        if "choices" not in data:
            return {
                "question": body.question,
                "answer": "Copilot is temporarily unavailable. Please try again shortly.",
                "data_used": {
                    "sessions_analyzed": total,
                    "failed_sessions": len(failed),
                    "clusters_found": len(clusters.data),
                },
            }

        answer = data["choices"][0]["message"]["content"]

    return {
        "question": body.question,
        "answer":   answer,
        "data_used": {
            "sessions_analyzed": total,
            "failed_sessions":   len(failed),
            "clusters_found":    len(clusters.data),
        },
    }