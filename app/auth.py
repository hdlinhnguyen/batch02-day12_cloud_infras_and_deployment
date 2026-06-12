from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
from app.config import settings

# Header name to check
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependency: verifying incoming requests contain the correct X-API-Key header.
    Returns the key if valid. Raises 401/403 errors otherwise.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include header: X-API-Key: <your-key>",
        )
    if api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )
    return api_key
