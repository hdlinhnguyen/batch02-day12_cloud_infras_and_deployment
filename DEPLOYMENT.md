# Deployment Information

## Public URL
- **Staging URL:** `https://your-agent.railway.app`
- **Platform:** Railway / Render

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
- [Staging Dashboard](screenshots/dashboard.png) - View deployed services and Redis database on the cloud panel.
- [Service Running Logs](screenshots/running.png) - App startup logs showing successful connection to Redis and local servers up.
- [Endpoint Validation Tests](screenshots/test.png) - Terminal logs of liveness, auth checks, rate limiting, and cost guard outputs.

