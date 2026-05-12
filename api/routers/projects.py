from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import secrets

from auth import verify_api_key
from database import get_db

router = APIRouter()


# ──────────────────────────────────────────
# PROJECT CREATION (called during onboarding)
# ──────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    org_id: Optional[str] = None


@router.post("/auth/projects")
def create_project(body: ProjectCreate):
    db = get_db()
    api_key = "ap_" + secrets.token_urlsafe(24)

    # Create org if not provided
    org_id = body.org_id
    if not org_id:
        org = db.table("organizations").insert({"name": f"{body.name} Org"}).execute()
        org_id = org.data[0]["id"]

    project = db.table("projects").insert({
        "org_id":  org_id,
        "name":    body.name,
        "api_key": api_key,
    }).execute()

    return {
        "project_id": project.data[0]["id"],
        "api_key":    api_key,
        "name":       body.name,
    }


# ──────────────────────────────────────────
# SESSIONS LIST
# ──────────────────────────────────────────

@router.get("/projects/{project_id}/sessions")
def get_sessions(
    project_id: str,
    page:   int = Query(1, ge=1),
    status: str = Query("all"),
    project: dict = Depends(verify_api_key),
):
    db     = get_db()
    limit  = 50
    offset = (page - 1) * limit

    query = (
        db.table("sessions")
        .select("*")
        .eq("project_id", project_id)
        .order("started_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if status != "all":
        query = query.eq("status", status)

    result = query.execute()
    return {"sessions": result.data, "page": page, "total": len(result.data)}


# ──────────────────────────────────────────
# SINGLE SESSION DETAIL
# ──────────────────────────────────────────

@router.get("/projects/{project_id}/sessions/{session_id}")
def get_session_detail(
    project_id: str,
    session_id: str,
    project: dict = Depends(verify_api_key),
):
    db      = get_db()
    session = (
        db.table("sessions")
        .select("*")
        .eq("id", session_id)
        .eq("project_id", project_id)
        .single()
        .execute()
    )
    events = (
        db.table("events")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return {**session.data, "events": events.data}


# ──────────────────────────────────────────
# AGGREGATE STATS
# ──────────────────────────────────────────

@router.get("/projects/{project_id}/stats")
def get_stats(
    project_id: str,
    project: dict = Depends(verify_api_key),
):
    db       = get_db()
    now      = datetime.now(timezone.utc)
    today    = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    # Sessions created today
    today_result = (
        db.table("sessions")
        .select("id", count="exact")
        .eq("project_id", project_id)
        .gte("started_at", today)
        .execute()
    )

    # Last 7 days for aggregates
    week_result = (
        db.table("sessions")
        .select("status, cost_usd, latency_ms")
        .eq("project_id", project_id)
        .gte("started_at", week_ago)
        .execute()
    )

    rows    = week_result.data or []
    total   = len(rows)
    success = sum(1 for r in rows if r["status"] == "success")
    avg_lat = int(sum(r["latency_ms"] or 0 for r in rows) / total) if total else 0
    total_cost = round(sum(float(r["cost_usd"] or 0) for r in rows), 4)

    sr = round(success / total, 3) if total else 0
    lat_score = max(0, 1 - avg_lat / 2000) * 100
    health_score = min(100, int(sr * 100 * 0.4 + lat_score * 0.3 + sr * 100 * 0.3))

    return {
        "sessions_today": today_result.count or 0,
        "avg_latency_ms": avg_lat,
        "success_rate":   sr,
        "health_score":   health_score,   # calculated, not from DB
        "total_cost_usd": total_cost,
    }


# ──────────────────────────────────────────
# INTENT CLUSTERS
# ──────────────────────────────────────────

@router.get("/projects/{project_id}/clusters")
def get_clusters(
    project_id: str,
    project: dict = Depends(verify_api_key),
):
    db       = get_db()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()

    result = (
        db.table("intent_clusters")
        .select("*")
        .eq("project_id", project_id)
        .gte("week", week_ago)
        .order("session_count", desc=True)
        .limit(10)
        .execute()
    )
    return {"clusters": result.data}


# ──────────────────────────────────────────
# ERRORS
# ──────────────────────────────────────────

@router.get("/projects/{project_id}/errors")
def get_errors(
    project_id: str,
    project: dict = Depends(verify_api_key),
):
    db = get_db()
    result = (
        db.table("sessions")
        .select("id, status")
        .eq("project_id", project_id)
        .eq("status", "failed")
        .execute()
    )

    failed = result.data or []
    if not failed:
        return {"errors": []}

    return {
        "errors": [{
            "type":               "Agent failure",
            "count":              len(failed),
            "pct":                100,
            "example_session_id": failed[0]["id"],
        }]
    }


# ──────────────────────────────────────────
# TRIGGER CLUSTERING (on-demand)
# ──────────────────────────────────────────

@router.post("/projects/{project_id}/cluster")
async def trigger_clustering(
    project_id: str,
    project: dict = Depends(verify_api_key),
):
    from clustering.pipeline import run_clustering_for_project
    clusters = await run_clustering_for_project(project_id)
    return {"clusters_created": len(clusters), "clusters": clusters}