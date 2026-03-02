# Exploring function calling with Google ADK

Function-calling with Python and Google ADK. This project demonstrates building a generative AI agent that interacts with external services (example: Google APIs) and performs function calls safely.     

## Available Services

✅ **Currently Working**: Agent scaffolding, Google API integrations (via service account credentials), local web UI (when available)

⚠️ **Requires Additional Setup / Approval**: Any third-party services that require account approval (voice callbacks, production APIs) or external hosting (Ollama, Runpod, etc.)

### Example prompts you can use with an agent built from this repo

- Send a search query to Google and summarize the top result for "recent advances in green hydrogen".
- Run a code-generation task to scaffold a small Flask app and return the file tree.
- "Look up the weather for Nairobi and return a 3-line summary for my user."


## Table of contents

- [File structure](#file-structure)
- [Attribution](#attribution)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Run in Docker](#run-in-docker)
- [API Reference](#api-reference)
- [Usage](#usage)
- [Logging](#logging)
- [Use cases](#use-cases)
- [Responsible AI Practices](#responsible-ai-practices)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)


## File structure

```text
.
├── agentops_agent/    # Communication agent with security guardrails
├── my_agent/          # Basic agent example
├── evals/             # Evaluation datasets
├── logs/              # Application and security logs
├── .dockerignore
├── .gitignore
├── DATASETS.md
├── GUARDRAILS.md      # Security guardrails documentation
├── Makefile
├── .env.example
├── your.json          # (example service account - do NOT commit)
├── requirements.txt
```

## Attribution

- [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) - agent framework and tooling      
- [Ruff](https://github.com/astral-sh/ruff) for linting code
- [uv](https://github.com/astral-sh/uv) Python package and project manager      
  

### License

This project is licensed under [Apache 2.0 License](https://github.com/Shuyib/adk-google-prac/blob/main/LICENSE).

## Installation

We recommend using Python 3.13 and `uv` for environment and dependency management.

1. Clone the repository

```bash
git clone https://github.com/Shuyib/adk-google-prac.git
cd adk-google-prac.git
```

2. Install `uv` (recommended via pipx) and create a venv

```bash
pipx install uv
uv venv --python 3.13
```

3. Activate the venv (optional) and install dependencies

```bash
source .venv/bin/activate
uv pip sync requirements.txt
```

Or, to install editable project + dev requirements (matching Makefile):

```bash
uv pip install -e . -r requirements-dev.txt
```

4. Skip the line

```bash
make install
```

5. Activate the venv

```bash
source .venv/bin/activate
```


## Environment Variables

Create a `.env` file in the project root (do NOT commit it). See `.env.example` for placeholders.

Required for Google integrations:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your.json
GOOGLE_CLOUD_PROJECT=nameyourprojectid
GOOGLE_CLOUD_LOCATION=punkrockfactory
GOOGLE_API_KEY=getfromvertexai
GOOGLE_GENAI_USE_VERTEXAI=1

# Required for agentops_agent (Africa's Talking integrations):
AT_USERNAME=your_username
AT_API_KEY=your_api_key
AGENT_MODE=interactive # or non-interactive
```

Ensure that you have this service account credentials JSON. This is your id to use the google cloud features. 

Setup Google Cloud project > Create a Service account > Download your service account key (JSON) > Setup GOOGLE CLOUD credentials      

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
```

**Where to find these values:**

- **GOOGLE_CLOUD_PROJECT**: In the Google Cloud Console, click the project dropdown (top-left) to see the **ID** of your project (e.g., `my-project-123`).
- **GOOGLE_CLOUD_LOCATION**: The region you want to use (e.g., `us-central1`, `europe-west4`). See [Vertex AI locations](https://cloud.google.com/vertex-ai/docs/general/locations).
- **GOOGLE_API_KEY**: Go to **APIs & Services > Credentials** > **+ CREATE CREDENTIALS** > **API key**. It is recommended to restrict this key to the "Vertex AI API".

## Run in Docker

Build and run the project in a container. Do NOT copy credentials into the image — mount them at runtime or use a secret manager.

1) Build using the Makefile:

```bash
make docker_build
```

2) Run locally (recommended — set `HOST_CREDENTIALS` to your host JSON path):

```bash
export HOST_CREDENTIALS=/absolute/path/to/at-project-XXXX.json
export AT_API_KEY=your_api_key        # optional
export AT_USERNAME=your_username     # optional
export AGENT_MODE=interactive       # or non-interactive
export GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/creds.json # Optional Google Cloud settings: service account credentials, API keys, project/location
export GOOGLE_CLOUD_PROJECT=nameyourprojectid 
export GOOGLE_CLOUD_LOCATION=punkrockfactory
export GOOGLE_GENAI_USE_VERTEXAI=1
export GOOGLE_API_KEY=getfromvertexai

make docker_run
```

This `make docker_run` uses secure defaults: mounts the credential file read-only into `/run/secrets/creds.json`, sets `GOOGLE_APPLICATION_CREDENTIALS`, runs the container with `--read-only`, `--tmpfs /tmp`, drops Linux capabilities, and maps port 80.

3) Stop the container:

```bash
make docker_stop
```

If you prefer to run `docker` directly, an example equivalent is:

```bash
docker build -t adk-agent:v0 .
docker run --rm -d \
    --name adk-agent \
    --user adkuser \
    --read-only \
    --tmpfs /tmp:rw,size=64m \
    --cap-drop ALL \
    --cap-add NET_BIND_SERVICE \
    --health-cmd="curl -f http://localhost/health || exit 1" \
    --health-interval=30s \
    -v "${HOST_CREDENTIALS}:/run/secrets/creds.json:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/creds.json \
    -e AT_API_KEY="${AT_API_KEY}" \
    -e AT_USERNAME="${AT_USERNAME}" \
    -e AGENT_MODE=interactive \
    -e GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}" \
    -e GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION}" \
    -e GOOGLE_GENAI_USE_VERTEXAI=1 \
    -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
    -p 80:80 \
    adk-agent:v0
```

For production, use your container orchestrator to mount secrets and enforce runtime hardening (read-only root, seccomp, AppArmor, dropped capabilities, resource limits).

## API Reference

Once the container is running (`make docker_run`), the ADK API server is available on **http://localhost:80**.

### Interactive docs

| URL | Description |
|-----|-------------|
| http://localhost:80/docs | Swagger UI — browse and try every endpoint |
| http://localhost:80/openapi.json | Raw OpenAPI 3 schema |
| http://localhost:80/health | Health check (`{"status":"ok"}`) |

### Typical workflow

All agent interactions follow three steps: **list apps → create session → run**.

#### 1. List available agents

```bash
curl http://localhost:80/list-apps
```

Example response:
```json
["agentops_agent", "my_agent"]
```

#### 2. Create a session

```bash
curl -X POST http://localhost:80/apps/agentops_agent/users/user-1/sessions \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Example response:
```json
{"id": "sess-abc123", "app_name": "agentops_agent", "user_id": "user-1", "state": {}, "events": []}
```

#### 3. Send a message (non-streaming)

```bash
curl -X POST http://localhost:80/run \
  -H 'Content-Type: application/json' \
  -d '{
    "app_name": "agentops_agent",
    "user_id": "user-1",
    "session_id": "sess-abc123",
    "new_message": {
      "role": "user",
      "parts": [{"text": "What time is it in Nairobi?"}]
    }
  }'
```

#### 4. Send a message (streaming via SSE)

```bash
curl -N -X POST http://localhost:80/run_sse \
  -H 'Content-Type: application/json' \
  -d '{
    "app_name": "agentops_agent",
    "user_id": "user-1",
    "session_id": "sess-abc123",
    "new_message": {
      "role": "user",
      "parts": [{"text": "Summarise the top Google result for green hydrogen."}]
    }
  }'
```

Each SSE event is a JSON object with an `content` or `actions` key. The stream ends with a `[DONE]` sentinel.

#### 5. Retrieve session history

```bash
curl http://localhost:80/apps/agentops_agent/users/user-1/sessions/sess-abc123
```

### Common environment variables passed to the API

| Variable | Purpose |
|----------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service-account JSON inside the container (`/run/secrets/creds.json`) |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI region (e.g. `us-central1`) |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set `1` to route through Vertex AI instead of AI Studio |
| `GOOGLE_API_KEY` | AI Studio API key (used when `GOOGLE_GENAI_USE_VERTEXAI=0`) |
| `AGENT_MODE` | `interactive` or `non-interactive` — controls model and confirmation behaviour |

> **Tip:** The full OpenAPI schema at `/openapi.json` is the authoritative reference for every endpoint, its request body, and all response shapes.

## Logging

- Handled by the toolkit. However, we recommend more logging and tracing inputs and outputs.
- <https://google.github.io/adk-docs/observability/logging/>


## Use cases

- Research assistant that summarizes web search results    
- Automated support workflows that send notifications (requires proper credentials)      
- Teaching examples for function-calling agents and safety layers


## Usage

Run the agent

Use `adk` CLI to scaffold and run agents provided by Google ADK:

```bash
# create an agent skeleton
adk create my_agent

# run the basic agent
adk run my_agent

# run the communication agent with guardrails
adk run agentops_agent
```

Web UI (if supported by the agent):
```bash
adk web
# then open http://localhost:8000
```

## Responsible AI practices

- Observability: <https://google.github.io/adk-docs/observability/agentops/>
- Evaluation: <https://google.github.io/adk-docs/evaluate/>
- Guardrails: See [GUARDRAILS.md](./GUARDRAILS.md) for our comprehensive security implementation, or read the [Google ADK Safety docs](https://google.github.io/adk-docs/safety/#in-tool-guardrails).

## Limitations

- Google ADK is evolving; some features may be experimental

## Troubleshooting

- Verify `.env` is present and loaded
- Check `GOOGLE_APPLICATION_CREDENTIALS` path and that the file exists
- Use `make show-env` to inspect key env variables without exposing secrets
- VPN prevents you from running any agents


## Contributing
Please open issues or PRs. Keep secrets out of the repo and add tests for agent behaviors where possible.