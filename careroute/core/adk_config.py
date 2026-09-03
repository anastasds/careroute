import os
from google import genai
from google.genai import types
from google.adk.models import Gemini
from google.adk.telemetry import TelemetryConfig
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "default-project-id")
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID

AGENT_ENGINE_ID = os.getenv("VERTEX_AGENT_ENGINE_ID", "123456789")
LOCATION = os.getenv("GCP_LOCATION", "us-central1")
ENABLE_MODEL_ARMOR = os.getenv("MODEL_ARMOR_ENABLED", "false").lower() in ("true", "1", "yes")

# Model Armor configuration with graceful bypass if disabled
if ENABLE_MODEL_ARMOR:
    safety_config = types.GenerateContentConfig(
        automatic_function_calling={"disable": True},
        model_armor_config=types.ModelArmorConfig(
            prompt_template_name=f"projects/{PROJECT_ID}/locations/{LOCATION}/templates/careroute-clinical-safety"
        )
    )
else:
    safety_config = types.GenerateContentConfig(
        automatic_function_calling={"disable": True}
    )

# Use Enterprise Platform or API key depending on environment
if "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"] != "mock-gemini-key":
    adk_client = genai.Client()
else:
    adk_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# Telemetry
adk_telemetry_config = TelemetryConfig(
    adk_experimental_telemetry_opt_in=True,
    capture_message_content="SPAN_AND_EVENT"
)

# Vertex AI Agent Platform Services
adk_session_service = VertexAiSessionService(
    project=PROJECT_ID,
    location=LOCATION,
    agent_engine_id=AGENT_ENGINE_ID
)
adk_memory_service = VertexAiMemoryBankService(
    project=PROJECT_ID,
    location=LOCATION,
    agent_engine_id=AGENT_ENGINE_ID
)

# Helper for creating ADK Gemini models with our safety config
def create_safe_model(model_name: str) -> Gemini:
    return Gemini(
        model=model_name,
        client=adk_client,
        client_kwargs={"config": safety_config}
    )
