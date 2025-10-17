
# AI App Generator Backend

## Overview
A FastAPI backend service that takes JSON requests with code generation prompts,
uses LLM APIs to generate code, creates a GitHub repository with generated files,
enables GitHub Pages, and notifies an evaluator endpoint.

## Setup

1. Clone repository
2. Create `.env` with your secrets (see below)
3. Install dependencies: `pip install -r requirements.txt`
4. Run locally: `uvicorn app.main:app --reload`

## Environment Variables
- APP_SECRET: Secret for validation
- AIPIPE_API_KEY: API key for AIPipe
- HUGGINGFACE_API_KEY: API key for Hugging Face
- GITHUB_TOKEN: GitHub PAT with repo, contents, and pages scopes
- BASE_REPO_OWNER: Your GitHub username

## Docker
Build: `docker build -t ai-app-generator .`
Run: `docker run -p 8000:8000 --env-file .env ai-app-generator`

## Notes
- Attachments are saved to /uploads/ but not yet integrated into LLM prompts.
- LLM fallback: AIPipe -> Hugging Face (gpt2 model).
- GitHub Pages enabled on main branch root.
