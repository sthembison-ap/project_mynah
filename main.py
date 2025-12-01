from orchestration.flow import run_orchestration
from schemas.context import OrchestrationRequest
import json

if __name__ == "__main__":
    request = OrchestrationRequest(message="I want to pay R500 per month towards my balance", 
                               debtor_id="123456789", 
                               session_id="session_abc123456",
                               )
    agent_response, orchestration_response = run_orchestration(request)
    print(json.dumps(orchestration_response.model_dump(), indent=2))
    print(json.dumps(agent_response.model_dump(), indent=2))