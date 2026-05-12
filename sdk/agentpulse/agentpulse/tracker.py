import time
import functools
import uuid
import threading
from typing import Optional
from .client import AgentPulseClient


class Tracker:
    def __init__(self):
        self._client: Optional[AgentPulseClient] = None

    def init(self, api_key: str, project_id: str, base_url: str = None):
        """Call once at app startup before any agents run."""
        self._client = AgentPulseClient(api_key, project_id, base_url)

    def trace(self, session_id: str = None):
        """
        Decorator factory. Usage:
            @tracker.trace(session_id=user_id)
            def my_agent(message: str) -> str: ...
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start      = time.perf_counter()
                sid        = session_id or str(uuid.uuid4())
                user_msg   = args[0] if args and isinstance(args[0], str) else ""
                status     = "success"
                agent_resp = ""
                result     = None

                try:
                    result     = func(*args, **kwargs)
                    agent_resp = str(result) if result else ""
                except Exception as e:
                    status     = "failed"
                    agent_resp = str(e)
                    raise  # always re-raise — never swallow user exceptions
                finally:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    if self._client:
                        payload = {
                            "session_id":     sid,
                            "user_message":   user_msg,
                            "agent_response": agent_resp,
                            "status":         status,
                            "latency_ms":     latency_ms,
                        }
                        # daemon=True: dies with main thread, never orphans
                        threading.Thread(
                            target=self._client.post_event_sync,
                            args=(payload,),
                            daemon=True
                        ).start()
                return result
            return wrapper
        return decorator


# Singleton — users import this one object
tracker = Tracker()