import httpx
from typing import Dict, Any

DEFAULT_BASE_URL = "https://astrik10-agentpulse-api.hf.space"

class AgentPulseClient:
    def __init__(self, api_key: str, project_id: str, base_url: str = None):
        self.project_id = project_id
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def post_event_sync(self, payload: Dict[str, Any]) -> None:
        """Runs in a daemon thread — never blocks the agent."""
        payload["project_id"] = self.project_id
        try:
            with httpx.Client(timeout=3.0) as c:
                c.post(
                    f"{self.base_url}/v1/track",
                    json=payload,
                    headers=self.headers
                )
        except Exception:
            pass  # Silent — never crash the agent