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

        # Save attachments and add to prompt
        att_files = save_attachments(task_request.attachments) if task_request.attachments else []
        attachments_info = ", ".join(att_files) if att_files else "No attachments"
        base_prompt = f"Generate a static HTML page (including HTML, CSS, and JavaScript if needed) to implement the following: {task_request.brief}. Attachments: {attachments_info}. Checks to satisfy: {task_request.checks}."

        # For round 2, fetch existing code and update
        repo_name = f"student-repo-{task_request.task}"
        if task_request.round == 2:
            gh = GitHubClient()
            try:
                repo = gh.gh.get_repo(f"{os.getenv('BASE_REPO_OWNER')}/{repo_name}")
                existing_code = repo.get_contents("index.html").decoded_content.decode()
                base_prompt = f"Update the following existing HTML code based on this new requirement: {task_request.brief}. Existing code: {existing_code}. Attachments: {attachments_info}. Checks to satisfy: {task_request.checks}."
            except GithubException as e:
                logger.warning(f"Could not fetch existing code for round 2: {str(e)}, generating new")

        code = generate_code_with_llm(base_prompt)
        logger.info("Code generated", extra={"nonce": task_request.nonce, "brief": task_request.brief})

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
            "README.md": f"# Generated App\nThis repository contains code generated based on the prompt:\n{task_request.brief}\n\nChecks: {task_request.checks}",
            "LICENSE": "MIT License\n\nCopyright (c) 2025 AI App Generator\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\n to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE."
        }

        # Create or update GitHub repo and push files
        gh = GitHubClient()
        repo_info = gh.create_repo_with_files(repo_name, repo_files)
        logger.info("Repository processed", extra={"nonce": task_request.nonce, "repo_url": repo_info["repo_url"]})

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
        logger.warning("Invalid secret received")
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
