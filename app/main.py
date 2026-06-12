import os
import sys
import time
import json
import uuid
import logging
import signal
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Add app directory to sys.path so nested imports resolve correctly
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis
import uvicorn

# Import local modules
from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import RedisRateLimiter
from app.cost_guard import RedisCostGuard
from app.providers import make_provider
from app.tools import load_tool_declarations, to_openai_tools
from app.chat import run_model_tool_loop

# Structured JSON logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# Server state
START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"agent-instance-{uuid.uuid4().hex[:6]}")
is_ready = False
in_flight_requests = 0

# Redis and Security Services (Initialized during startup)
r_client = None
rate_limiter = None
cost_guard = None

# Day 04 Research Agent Artifacts
system_prompt = ""
openai_tools = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_ready, r_client, rate_limiter, cost_guard, system_prompt, openai_tools
    
    # ── Startup ──
    logger.info(f"Starting instance {INSTANCE_ID} in {settings.environment} mode...")
    
    # Connect to Redis
    try:
        r_client = redis.from_url(settings.redis_url, decode_responses=True)
        r_client.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}. Falling back to in-memory mode (not scalable!).")
        r_client = None

    # Initialize rate limiter & cost guard
    rate_limiter = RedisRateLimiter(r_client, max_requests=settings.rate_limit_per_minute, window_seconds=60)
    cost_guard = RedisCostGuard(r_client, monthly_budget_usd=settings.monthly_budget_usd)

    # Load Day 04 artifacts
    try:
        prompt_path = APP_DIR / "artifacts" / "system_prompt.md"
        tools_path = APP_DIR / "artifacts" / "tools.yaml"
        system_prompt = prompt_path.read_text(encoding="utf-8")
        tool_declarations = load_tool_declarations(tools_path)
        openai_tools = to_openai_tools(tool_declarations)
        logger.info("Successfully loaded system prompt and tool declarations.")
    except Exception as e:
        logger.error(f"Error loading prompt/tools artifacts: {e}")
        # Default fallback
        system_prompt = "You are a helpful research assistant."
        openai_tools = []

    is_ready = True
    logger.info(f"Instance {INSTANCE_ID} ready.")
    
    yield
    
    # ── Shutdown ──
    is_ready = False
    logger.info(f"Shutdown signal received on {INSTANCE_ID}. Waiting for active requests to drain...")
    
    # Wait for in-flight requests to complete (max 30s)
    timeout = 30
    elapsed = 0
    while in_flight_requests > 0 and elapsed < timeout:
        logger.info(f"Waiting for {in_flight_requests} active requests...")
        time.sleep(1)
        elapsed += 1
        
    if r_client is not None:
        try:
            r_client.close()
            logger.info("Closed Redis connection.")
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
            
    logger.info("Shutdown complete.")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Request tracking middleware (for graceful shutdown)
@app.middleware("http")
async def track_requests(request: Request, call_next):
    global in_flight_requests
    in_flight_requests += 1
    try:
        response = await call_next(request)
        return response
    finally:
        in_flight_requests -= 1

# Security headers middleware
@app.middleware("http")
async def inject_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if "server" in response.headers:
        del response.headers["server"]
    return response

# Pydantic models
class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=1, max_length=1000)

# Stateless History Helpers
def load_history(user_id: str) -> list[dict[str, str]]:
    if r_client is not None:
        try:
            data = r_client.get(f"history:{user_id}")
            return json.loads(data) if data else []
        except Exception as e:
            logger.warning(f"Failed to read history from Redis: {e}")
    return []

def save_history(user_id: str, history: list[dict[str, str]], ttl: int = 86400):
    if len(history) > 20:
        history = history[-20:]
    if r_client is not None:
        try:
            r_client.setex(f"history:{user_id}", ttl, json.dumps(history))
        except Exception as e:
            logger.warning(f"Failed to write history to Redis: {e}")

# Endpoints
@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "instance_id": INSTANCE_ID,
        "status": "running"
    }

@app.post("/ask")
async def ask_endpoint(
    body: AskRequest,
    _key: str = Depends(verify_api_key)
):
    """
    Main Protected Agent Endpoint:
    1. Validates API Key via Header X-API-Key
    2. Enforces Redis Rate Limiter
    3. Enforces Redis Cost Guard
    4. Retrieves Stateless Conversation History from Redis
    5. Executes Day 04 Research Agent tool loop
    6. Saves Conversation History
    7. Records Cost Usage in Redis
    """
    user_id = body.user_id
    question = body.question

    # Enforce Rate Limiting
    rate_info = rate_limiter.check(user_id)

    # Enforce Cost Guard budget check
    cost_guard.check_budget(user_id)

    # Retrieve history from Redis
    history = load_history(user_id)

    # Build messages block
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": question}
    ]

    logger.info(json.dumps({
        "event": "ask_request",
        "user_id": user_id,
        "question_length": len(question),
        "history_length": len(history)
    }))

    # Execute Day 04 Research Agent with fallback to Mock LLM
    try:
        provider = make_provider(settings.provider_name)
        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=settings.model_name,
            max_tool_rounds=4
        )
        answer = result.get("assistant_text") or "No response text generated."
        # Estimate token usage based on word counts
        input_tokens = len(question.split()) * 2 + sum(len(m["content"].split()) * 2 for m in history)
        output_tokens = len(answer.split()) * 2
    except Exception as e:
        logger.warning(f"Model/Provider loop execution error: {e}. Falling back to mock LLM.")
        from utils.mock_llm import ask as mock_ask
        answer = mock_ask(question)
        input_tokens = len(question.split()) * 2
        output_tokens = len(answer.split()) * 2
        result = {
            "status": "answered_fallback",
            "error": str(e)
        }

    # Save update history
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    save_history(user_id, history)

    # Record cost usage
    new_cost = cost_guard.record_usage(user_id, input_tokens, output_tokens)

    logger.info(json.dumps({
        "event": "ask_response",
        "user_id": user_id,
        "answer_length": len(answer),
        "new_monthly_cost": new_cost
    }))

    return {
        "question": question,
        "answer": answer,
        "served_by": INSTANCE_ID,
        "usage": {
            "rate_limit_remaining": rate_info["remaining"],
            "monthly_cost_usd": new_cost,
            "budget_usd": settings.monthly_budget_usd
        }
    }

@app.get("/health")
def health_probe():
    uptime = round(time.time() - START_TIME, 1)
    
    # Optional dependency checks (e.g. psutil memory)
    checks = {}
    try:
        import psutil
        mem = psutil.virtual_memory()
        checks["memory"] = {
            "status": "ok" if mem.percent < 90 else "degraded",
            "used_percent": mem.percent
        }
    except ImportError:
        checks["memory"] = {"status": "ok", "note": "psutil not installed"}

    overall_status = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    
    return {
        "status": overall_status,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": uptime,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks
    }

@app.get("/ready")
def readiness_probe():
    if not is_ready:
        raise HTTPException(status_code=503, detail="Agent is starting up or shutting down.")
    
    # Verify Redis connectivity
    if r_client is not None:
        try:
            r_client.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="Redis connection unavailable.")
            
    return {
        "ready": True,
        "instance_id": INSTANCE_ID
    }

# Handle OS signals to trigger uvicorn lifecycle shutdown
def handle_sigterm(signum, frame):
    logger.info(f"Received signal {signum} — initiating graceful shutdown sequence.")

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

if __name__ == "__main__":
    logger.info(f"Launching FastAPI application on {settings.host}:{settings.port}")
    uvicorn.run(
        "main:app" if settings.debug else app,
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=30
    )
