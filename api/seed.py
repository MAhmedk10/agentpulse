# api/seed.py
import httpx
import asyncio

API_KEY = "ap__RN2TdOV4yBuzOMg5hmc3UJVIjHR6pD6"
BASE    = "http://localhost:8000"

messages = [
    ("sess-002", "What is the difference between free and paid plans?"),
    ("sess-003", "Can I get a refund for my subscription?"),
    ("sess-004", "How do I cancel my account?"),
    ("sess-005", "How do I connect the SDK to my agent?"),
    ("sess-006", "Where is the API documentation?"),
    ("sess-007", "I am getting a 401 error when calling the API"),
    ("sess-008", "My agent is returning wrong answers"),
    ("sess-009", "How do I export my session data?"),
    ("sess-010", "Do you support LangChain integration?"),
    ("sess-011", "What models does AgentPulse support?"),
]

async def seed():
    async with httpx.AsyncClient() as client:
        for session_id, message in messages:
            r = await client.post(
                f"{BASE}/v1/track",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "session_id":     session_id,
                    "user_message":   message,
                    "agent_response": "Here is the answer to your question.",
                    "status":         "success",
                    "latency_ms":     800,
                },
            )
            print(f"{session_id}: {r.json()}")

asyncio.run(seed())