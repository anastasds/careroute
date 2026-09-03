import asyncio
from careroute.core.adk_config import adk_session_service

async def test():
    try:
        session = await adk_session_service.create_session("test-vertex-session-123", "test-user")
        print("Successfully created Vertex AI session:", session.id)
    except Exception as e:
        print("Error creating session:", type(e).__name__, e)

asyncio.run(test())
