import os
import logging
import httpx
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.models import TaskRequest
from app.github_client import GitHubClient
from app.tasks import save_attachments
from app.llm_handler import generate_code_with_llm
from app.utils import setup_logging, log_request

logger = setup_logging()

app = FastAPI(title="AI Code Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET = os.getenv("APP_SECRET")

def validate_secret(secret: str):
    if SECRET is None:
        logger.warning("APP_SECRET not set, allowing all requests (dev mode)")
        return True
    return secret == SECRET

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True
)
async def send_callback(evaluation_url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(evaluation_url, json=payload, timeout=30.0)
        response.raise_for_status()
    logger.info("Callback sent successfully", extra={"evaluation_url": evaluation_url, "payload": payload})

async def background_process(task_request: TaskRequest):
    try:
        # Debug environment variables
        logger.info("Environment variables in background task", extra={
            "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
            "BASE_REPO_OWNER": os.getenv("BASE_REPO_OWNER")
        })

        # Generate HTML page explicitly
        html_prompt = f"Generate a static HTML page (including HTML, CSS, and JavaScript if needed) to implement the following: {task_request.brief}. Do not generate Python or other server-side code unless explicitly requested."
        code = await generate_code_with_llm(html_prompt)
        logger.info("Code generated", extra={"nonce": task_request.nonce, "brief": task_request.brief, "generated_code": code})

        # Ensure HTML output
        if not code.lower().startswith(("<!doctype html", "<html")):
            code = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Generated Page</title></head>
            <body>
                <h1>Generated Output</h1>
                <pre>{code}</pre>
            </body>
            </html>
            """

        # Prepare files for GitHub repo
        repo_files = {
            "index.html": code,
            "README.md": f"# Generated App\nThis repository contains a static HTML page generated based on the prompt:\n{task_request.brief}",
            "LICENSE": "MIT License\n\nCopyright (c) 2025 AI App Generator\n\nPermission is hereby granted..."
        }

        # Create GitHub repo and push files
        gh = GitHubClient()
        repo_name = f"student-repo-{uuid.uuid4().hex[:8]}"
        repo_info = gh.create_repo_with_files(repo_name, repo_files)
        logger.info("Repository created", extra={"nonce": task_request.nonce, "repo_url": repo_info["repo_url"]})

        # Notify evaluation_url
        payload = {
            "email": task_request.email,
            "task": task_request.task,
            "round": task_request.round,
            "nonce": task_request.nonce,
            "repo_url": repo_info["repo_url"],
            "commit_sha": repo_info["commit_sha"],
            "pages_url": repo_info["pages_url"]
        }
        await send_callback(task_request.evaluation_url, payload)
    except Exception as e:
        logger.error("Background process failed", extra={"nonce": task_request.nonce, "error": str(e)})
        raise

@app.post("/api/generate")
async def api_generate(task_request: TaskRequest, background_tasks: BackgroundTasks):
    if not validate_secret(task_request.secret):
        logger.warning("Invalid secret received", extra={"nonce": task_request.nonce})
        raise HTTPException(status_code=401, detail="Invalid secret")

    log_request(task_request.dict())

    # Save attachments if any
    att_files = save_attachments(task_request.attachments) if task_request.attachments else []
    logger.info("Attachments processed", extra={"nonce": task_request.nonce, "attachment_count": len(att_files)})

    background_tasks.add_task(background_process, task_request)

    return JSONResponse(status_code=200, content={
        "status": "accepted",
        "message": "Code generation started, repository will be created shortly"
    })

@app.get("/")
async def root():
    return {"message": "AI App Generator is running! Use /api/generate to submit tasks."}
