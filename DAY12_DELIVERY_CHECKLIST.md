#  Delivery Checklist — Day 12 Lab Submission

> **Student Name:** Nguyen Ho Dieu Linh  
> **Student ID:** 2A202600567  
> **Date:** 2026-06-12

---

##  Submission Requirements

Submit a **GitHub repository** containing:

### 1. Mission Answers (40 points)

Create a file `Report.md` with your answers to all exercises:

````markdown
# Day 12 Lab - Mission Answers

> **Student Name:** Nguyen Ho Dieu Linh  
> **Student ID:** 2A202600567  
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
````

---

### 2. Full Source Code - Lab 06 Complete (60 points)

Your final production-ready agent with all files:

```
your-repo/
├── app/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration
│   ├── auth.py              # Authentication
│   ├── rate_limiter.py      # Rate limiting
│   └── cost_guard.py        # Cost protection
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway config (or render.yaml)
└── README.md                # Setup instructions
```

**Requirements:**
-  All code runs without errors
-  Multi-stage Dockerfile (image < 500 MB)
-  API key authentication
-  Rate limiting (10 req/min)
-  Cost guard ($10/month)
-  Health + readiness checks
-  Graceful shutdown
-  Stateless design (Redis)
-  No hardcoded secrets

---

### 3. Service Domain Link

Create a file `DEPLOYMENT.md` with your deployed service information:

````markdown
# Deployment Information

## Public URL
- **Staging URL:** `https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app`
- **Platform:** Railway

---

## Local Deployment & Verification (Docker Compose)

You can launch and test the entire multi-replica stateless setup locally using Docker Compose.

### 1. Build and Run the Stack
Copy and complete `.env.example` into a local `.env.production` or configuration (or pass it through shell envs), then execute:
```bash
docker compose up --build -d
```
This starts:
- 3 replicas of `agent` (listening internally on port 8000).
- 1 container of `redis` (serving as stateless history cache and rate limit database).
- 1 container of `nginx` (acting as load balancer, exposing port `8888` or `8080` to the host).

### 2. Verify Health Probes
```bash
# Liveness probe
curl http://localhost:8080/health
# Expected output: {"status": "ok", "uptime_seconds": ..., "version": "1.0.0", ...}

# Readiness probe
curl http://localhost:8080/ready
# Expected output: {"ready": true, "instance_id": "..."}
```

### 3. Verify API Authentication
```bash
# Expect HTTP 401 (Missing API key)
curl -i -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'

# Expect HTTP 200 (Success with X-API-Key)
curl -i -X POST http://localhost:8080/ask \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_01", "question": "Explain Docker in one sentence"}'
```

### 4. Verify Rate Limiting
Execute this loop continuously to send 15 parallel requests:
```bash
for i in {1..15}; do
  curl -s -X POST http://localhost:8080/ask \
    -H "X-API-Key: my-secret-key" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "test_user_01", "question": "Request '$i'"}'
  echo ""
done
# You should receive 200 responses for the first 10 requests, and HTTP 429 (Too Many Requests) for subsequent ones.
```

### 5. Verify Stateless Scaling (Nginx load balancing)
Call the ask endpoint multiple times with the same `user_id` and trace the `"served_by"` value in the JSON response:
```bash
curl -s -X POST http://localhost:8080/ask \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_01", "question": "Tell me about load balancing"}'
```
You will notice the requests are distributed round-robin among different instances (e.g., `agent-instance-abc`, `agent-instance-xyz`), but conversation history is successfully loaded and maintained via Redis!

---

## Cloud Deployment (Railway)

### 1. Initialize and link Railway CLI
```bash
railway login
railway init
```

### 2. Provision Redis Add-on
In your Railway project panel:
1. Click **New** -> **Database** -> **Add Redis**.
2. Railway will automatically provision a Redis instance and set the `REDIS_URL` environment variable.

### 3. Setup Environment Variables
Run these commands to configure environment settings (replace values with your actual keys):
```bash
railway variables set ENVIRONMENT=production
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-super-secret-production-key
railway variables set PROVIDER_NAME=openrouter
railway variables set MODEL_NAME=openai/gpt-4o-mini
railway variables set OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...
railway variables set TAVILY_API_KEY=tvly-dev-xxxxxx...
```

### 4. Deploy code
```bash
railway up
```
Railway will automatically detect the root `Dockerfile` and perform a multi-stage production build. Once ready, check logs via CLI:
```bash
railway logs
```

### 5. Streamlit Web Interface Deployment (Day 04 Research Agent)
A secondary frontend service has been deployed in the same Railway project to expose the interactive Streamlit user interface:
- **Service Name:** `day04-web`
- **Root Directory:** `Day04-C401-Prompt-Engineering-Tool-Calling-Labs-student/starter_v0`
- **Public URL:** `https://day04-web-production.up.railway.app`
- **Environment variables configured:**
  ```bash
  PORT=8501
  OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx...
  TAVILY_API_KEY=tvly-dev-xxxxxxxx...
  FIRECRAWL_API_KEY=fc-xxxxxxxx...
  RAPIDAPI_KEY=xxxxxxxx...
  RAPIDAPI_TWITTER_HOST=twitter-api45.p.rapidapi.com
  ARXIV_USER_AGENT=AI20k-Day04-Research-Agent/1.0 (Table D1)
  ```

---

## Screenshots (Refer to screenshots/ folder)
- [Staging Dashboard](screenshots/dashboard_railway.png) - View deployed services and Redis database on the cloud panel.
- [Service running](screenshots/Deploy_Railway.png) - Service build and running status on Railway.
- [CI/CD Workflow Proof](screenshots/CICD proof_screenshot.png) - GitHub Actions CI/CD run and unit test execution logs.
````

##  Pre-Submission Checklist

- [x] Repository is public (or instructor has access)
- [x] `Report.md` completed with all exercises
- [x] `DEPLOYMENT.md` has working public URL
- [x] All source code in `app/` directory
- [x] `README.md` has clear setup instructions
- [x] No `.env` file committed (only `.env.example`)
- [x] No hardcoded secrets in code
- [x] Public URL is accessible and working
- [x] Screenshots included in `screenshots/` folder
- [x] Repository has clear commit history

---

##  Self-Test

Before submitting, verify your deployment:

```bash
# 1. Health check
curl https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app/health

# 2. Authentication required
curl https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app/ask
# Should return 401

# 3. With API key works
curl -H "X-API-Key: agentapikey" https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app/ask \
  -X POST -d '{"user_id":"test","question":"Hello"}'
# Should return 200

# 4. Rate limiting
for i in {1..15}; do 
  curl -H "X-API-Key: agentapikey" https://batch02-day12cloudinfrasanddeployment-production-39ce.up.railway.app/ask \
    -X POST -d '{"user_id":"test","question":"test"}'; 
done
# Should eventually return 429
```

---

##  Submission

**Submit your GitHub repository URL:**

```
https://github.com/hdlinhnguyen/batch02-day12_cloud_infras_and_deployment
```

**Deadline:** 17/4/2026

---

##  Quick Tips

1.  Test your public URL from a different device
2.  Make sure repository is public or instructor has access
3.  Include screenshots of working deployment
4.  Write clear commit messages
5.  Test all commands in DEPLOYMENT.md work
6.  No secrets in code or commit history

---

##  Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum

---

**Good luck! **
