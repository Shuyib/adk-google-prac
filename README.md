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
├── my_agent
├── .dockerignore
├── .gitignore
├── Makefile
├── .env.example
├── your.json  # (example service account - do NOT commit)
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
```

Ensure that you have this service account credentials JSON. This is your id to use the google cloud features. 

Setup Google Cloud project > Create a Service account > Download your service account key (JSON) > Setup GOOGLE CLOUD credentials      

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
```

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

# run a named agent (or use `adk run` per your project's entry points)
adk run my_agent
```

Web UI (if supported by the agent):
```bash
adk web
# then open http://localhost:8000
```

## Responsible AI practices

- Observability: <https://google.github.io/adk-docs/observability/agentops/>
- Evaluation: <https://google.github.io/adk-docs/evaluate/>
- Guadrails: <https://google.github.io/adk-docs/safety/#in-tool-guardrails>

## Limitations

- Google ADK is evolving; some features may be experimental

## Troubleshooting

- Verify `.env` is present and loaded
- Check `GOOGLE_APPLICATION_CREDENTIALS` path and that the file exists
- Use `make show-env` to inspect key env variables without exposing secrets
- VPN prevents you from running any agents


## Contributing
Please open issues or PRs. Keep secrets out of the repo and add tests for agent behaviors where possible.
