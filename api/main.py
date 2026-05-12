from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import events, projects,copilot


load_dotenv()

app = FastAPI(title='AgentPulse API', version='1.0.0')

app.add_middleware(CORSMiddleware,
    allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

app.include_router(events.router,   prefix="/v1", tags=["Events"])
app.include_router(projects.router, prefix="/v1", tags=["Projects"])
app.include_router(copilot.router, prefix="/v1", tags=["copilot"])

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '1.0.0'}# redeployed
