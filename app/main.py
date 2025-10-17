from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from app.models import GenerateRequest
from app.tasks import save_attachments
from app.github_client import create_or_update_repo
from app.llm_handler import generate_code
from app.utils import setup_logging, log_request
import logging
import os
import httpx

app = FastAPI()
logger = setup_logging()

@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Application starting up")
        required_env_vars = ["APP_SECRET", "GITHUB_TOKEN", "BASE_REPO_OWNER"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"Missing environment variables: {missing_vars}")
            raise ValueError(f"Missing environment variables: {missing_vars}")
        logger.info("Environment variables validated")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "AI App Generator is running! Use /api/generate to submit tasks."}

@app.post("/api/generate")
async def generate(request: GenerateRequest):
    try:
        log_request(request.dict())
        if request.secret != os.getenv("APP_SECRET"):
            raise HTTPException(status_code=401, detail="Invalid secret")
        
        attachment_paths = save_attachments(request.attachments)
        
        code = await generate_code(request.brief, attachment_paths)
        
        repo_name = f"student-repo-{request.task}"
        repo_url, commit_sha, pages_url = create_or_update_repo(
            repo_name, code, request.checks, request.round
        )
        
        callback_data = {
            "email": request.email,
            "task": request.task,
            "round": request.round,
            "nonce": request.nonce,
            "repo_url": repo_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(request.evaluation_url, json=callback_data)
            response.raise_for_status()
            logger.info("Callback sent successfully", extra={"url": request.evaluation_url})
        
        return {"status": "accepted", "message": "Code generation started, repository will be created shortly"}
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
