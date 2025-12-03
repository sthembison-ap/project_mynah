from orchestration.flow import run_orchestration
from schemas.context import OrchestrationRequest
import json
from routes.routes import router as api_router
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="Project Mynah Agent API",
    version="0.1.0",
    description="API wrapper around the LangChain-based mynah agent system.",
)

# Get the directory where main.py is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount the interaction endpoints
app.include_router(api_router, prefix="/api/v1")

# ---------- Serve Chat UI ----------
@app.get("/")
async def serve_chat_ui():
    """Serve the chat UI HTML file."""
    return FileResponse(os.path.join(BASE_DIR, "chat", "chat_ui.html"))

if __name__ == "__main__":
    # request = OrchestrationRequest(message="I want to pay R500 per month towards my balance", 
    #                             debtor_id="123456789", 
    #                             session_id="session_abc123456",
    #                             channel="webchat", #Added for the API endpoint
    #                            )
    # agent_response, nlu_agent_response, orchestration_response = run_orchestration(request)
    
    
    # print(json.dumps(orchestration_response.model_dump(), indent=2))
    # print("Testing Context Dump:")
    # print(json.dumps(agent_response.model_dump(), indent=2))
    #print(json.dumps(nlu_agent_response.model_dump(), indent=2))
    
    #####API Server Section#####
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
    #message="I want to pay R500 per month towards my balance"