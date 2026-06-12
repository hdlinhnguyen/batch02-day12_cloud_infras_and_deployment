# Day 12 Lab - Mission Answers

> **Student Name:** Nguyen Ho Dieu Linh  
> **Student ID:** AICB-P1-Student  
> **Date:** 2026-06-12  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`
1. **API Key & Database URL Hardcoded** (Lines 17-18): Secret credentials (`OPENAI_API_KEY`, `DATABASE_URL`) are stored directly in the source code. If pushed to GitHub, these keys will be leaked instantly.
2. **Lack of Centralized Configuration Management** (Lines 21-22): Parameters like `DEBUG = True` and `MAX_TOKENS = 500` are hardcoded in the application script instead of being read from environment variables or a configuration class.
3. **Unstructured Console Printing instead of Proper Logging** (Lines 33-34): The code uses Python's standard `print()` function for debugging. Not only is this hard to parse by log management tools, but it also leaks the sensitive `OPENAI_API_KEY` into the standard output logs.
4. **No Health Check Endpoints**: The application lacks `/health` (liveness) and `/ready` (readiness) check endpoints. In a production cloud environment, the container orchestrator (e.g., Railway/Render) has no way of detecting if the application has hung or crashed to restart it automatically.
5. **Hardcoded Port and Localhost Binding** (Lines 51-53): The server is bound to `host="localhost"` and a fixed `port=8000`. Inside a Docker container, binding to `localhost` restricts external access (it must bind to `0.0.0.0`), and hardcoding the port prevents cloud platforms from assigning dynamic ports via the `PORT` environment variable.
6. **No Graceful Shutdown Handling**: The server stops abruptly when killed, which abruptly aborts all active/in-flight requests, potentially leaving transactions or states corrupted.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
| :--- | :--- | :--- | :--- |
| **Config** | Hardcoded values in source code. | Loaded dynamically from environment variables (using a `Settings` class/Pydantic). | Enables security (no secrets in git) and portability (deploying the exact same build/image to staging vs production by changing environment variables). |
| **Health check** | None. | Exposes `/health` (liveness) and `/ready` (readiness) endpoints. | Allows cloud platforms / load balancers to detect crashed instances and avoid routing user traffic to containers that are not yet initialized (e.g., during startup/model loading). |
| **Logging** | `print()` statements. | Structured JSON logs using Python's `logging` module. | Makes it easy for log collectors (Loki, Datadog) to parse, filter, and query logs. Prevents logging secrets, and standardizes level (INFO/ERROR/WARN). |
| **Shutdown** | Abrupt exit on kill (SIGTERM / SIGINT). | Graceful shutdown handler catches signal, stops accepting new connections, and waits for current requests to finish. | Prevents request drops during deployment or scaling, ensuring zero downtime and preventing database or session state corruption. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** The base image is `python:3.11`. This is a full Debian-based image that includes development headers, build tools, and a full Python environment (~1 GB in size).
2. **Working directory:** The working directory is `/app` (configured using `WORKDIR /app`). Inside the container, this is the default folder where succeeding commands are executed.
3. **Why copy requirements.txt first?** This takes advantage of Docker's layer caching mechanism. Since project dependencies (`requirements.txt`) change far less frequently than the source code (`app.py`), copying and building dependencies first ensures that Docker caches this heavy layer. If you change a line of code in `app.py`, Docker will reuse the cached dependencies layer and build in seconds, instead of reinstalling pip packages.
4. **CMD vs ENTRYPOINT difference:**
   - `CMD`: Specifies the default executable and parameters for a container. It can be easily overridden by passing arguments at the end of the `docker run` command (e.g. `docker run my-image python other_script.py`).
   - `ENTRYPOINT`: Defines a command that will *always* run when the container starts. Any arguments passed via `docker run` or specified in `CMD` are appended to `ENTRYPOINT`. It is harder to override (requires the `--entrypoint` flag).

### Exercise 2.3: Image size comparison
- **Develop Image Size:** ~1.01 GB (using full `python:3.11` base image).
- **Production Image Size:** ~143 MB (using `python:3.11-slim` and multi-stage building).
- **Difference:** ~85.8% reduction in size.
- **Stage 1 (Builder) description:** Stage 1 uses a `slim` image, installs temporary build-essential utilities (like gcc, libpq-dev), and installs dependencies into `/root/.local`. It is used solely to build the packages.
- **Stage 2 (Runtime) description:** Stage 2 copies *only* the compiled packages from `/root/.local` in Stage 1 and the application source code. It throws away the compilers, cache files, and build tools. It runs the app using a secure non-root user (`appuser`).
- **Why is the production image smaller?** It uses `slim` (which strips out hundreds of MBs of unused system utilities) and discards the build tools, compilers, and pip installation caches used in the builder stage.

### Exercise 2.4: Docker Compose questions
- **Architecture Diagram:**
  ```
               ┌───────────────────────┐
               │  Nginx Load Balancer  │  (Port 80/443 exposed to public)
               └───────────┬───────────┘
                           │
             ┌─────────────┼─────────────┐ (Traffic split round-robin)
             ▼             ▼             ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │  Agent 1  │ │  Agent 2  │ │  Agent 3  │ (FastAPI replicas)
       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
             │             │             │
             └─────────────┼─────────────┘ (Communicate via internal network)
                           ▼
                     ┌───────────┐
                     │   Redis   │ (Session store & Rate limits)
                     └───────────┘
  ```
- **Services started:** `nginx` (reverse proxy / load balancer), `agent` (replicated Fast API servers), and `redis` (session memory database).
- **How they communicate:** They communicate over a custom private Docker bridge network (`internal` or `agent_net`). Nginx forwards external traffic on port 80/443 to the agents on port 8000 using service-name DNS resolution (`http://agent:8000`). The agents contact Redis at `redis:6379`. Redis is completely private; its port 6379 is not exposed to the host machine.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- **URL:** `https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app`
- **Screenshot:** [Link to screenshot in repo](screenshots/dashboard_railway.png)

### Exercise 3.2: Railway.toml vs Render.yaml
- **`railway.toml`:** A service-specific config file focused solely on the build and run execution parameters (such as `startCommand`, `healthcheckPath`, and restart policies) of the current service. It does not define infrastructure resources (databases, redis clusters, other services).
- **`render.yaml`:** An Infrastructure-as-Code Blueprint specification. It defines the entire system topology in one file (including Web Services, Databases, Redis clusters, private disks, regions, pricing tiers, and direct environment variables linking).

---

## Part 4: API Security

### Exercise 4.1: API Key authentication
- **Where is the API key checked?** It is checked in the `verify_api_key` dependency function in `app/auth.py`. It uses the `APIKeyHeader` to extract the `X-API-Key` HTTP header and compares it to the value loaded from the `AGENT_API_KEY` environment variable.
- **What happens if incorrect?**
  - If the header is missing: HTTP `401 Unauthorized` is returned with detail `"Missing API key"`.
  - If the header value is wrong: HTTP `403 Forbidden` is returned with detail `"Invalid API key"`.
- **How to rotate key?** Since `AGENT_API_KEY` is loaded dynamically from environment variables, you can rotate the key by updating the variable on the Railway/Render dashboard and triggering a redeployment/restart of the containers. No source code changes are required.

### Exercise 4.3: Rate Limiting
- **Algorithm used:** **Sliding Window Counter** (implemented using a list/deque of timestamps for each user inside Redis/memory).
- **Limit:** 10 requests per minute per user.
- **How to bypass for admin:** In the dependency or middleware, check the user's role (e.g. from token payload). If the role is `"admin"`, skip calling the rate-limiter check, or use an admin-specific rate limiter instance with a higher limit (e.g. 100 requests per minute).

### Exercise 4.4: Cost Guard implementation
- **Approach:**
  - Track monthly token spend in Redis under the key `cost:{user_id}:{YYYY-MM}`.
  - Before making an LLM request, fetch the current cost from Redis. If `current_cost + estimated_request_cost > budget` ($10), raise `HTTPException(402, "Monthly budget exceeded")`.
  - After the LLM request returns, compute the actual cost of the prompt and completion tokens (based on GPT-4o-mini rates: $0.15/1M input tokens, $0.60/1M output tokens).
  - Update the user's total cost in Redis using `INCRBYFLOAT` and set a key expiration (TTL) of 35 days.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
- **Health Checks:** `/health` acts as a liveness probe returning HTTP 200 `{"status": "ok"}` when the process is up. `/ready` acts as a readiness probe, checking if the Redis client can successfully run `ping()`. If Redis is down, it returns HTTP 503 `{"ready": false}`.
- **Graceful Shutdown:** Implemented using Fast API `lifespan` manager and a request tracking middleware. Upon receiving `SIGTERM`, `is_ready` is set to `False` (making the server fail readiness checks so load balancers stop sending new traffic), and it sleeps in a loop until all in-flight requests count (`_in_flight_requests`) drops to 0 (or a timeout of 30 seconds is reached) before closing Redis connections and exiting.
- **Stateless Design:** All conversation histories are stored as JSON-serialized lists in Redis (`history:{user_id}`) instead of memory.
- **Load Balancing:** Nginx distributes incoming chat traffic across 3 running agent instances using a round-robin strategy. Because the conversation history is stored in Redis (stateless design), a user can hit Agent 1, Agent 2, or Agent 3 on subsequent requests, and the agent will always retrieve their correct chat history from Redis.
- **Stateless Verification:** Verified by calling `/ask` multiple times, killing a random agent container, and observing that subsequent calls successfully retrieve history and proceed without error.
