import os
import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

AIPIPE_API_KEY = os.getenv("AIPIPE_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def call_aipipe(brief: str) -> str:
    headers = {"Authorization": f"Bearer {AIPIPE_API_KEY}"}
    json_payload = {"prompt": brief}
    response = httpx.post("https://api.aipipe.com/generate", json=json_payload, headers=headers, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    code = data.get("generated_code") or data.get("code") or data.get("output", "")
    if not code:
        raise ValueError("No code in AIPipe response")
    return code

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def call_huggingface(brief: str) -> str:
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    json_payload = {"inputs": brief}
    response = httpx.post("https://api-inference.huggingface.co/models/gpt2", json=json_payload, headers=headers, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list) and len(data) > 0:
        code = data[0].get("generated_text", "")
    else:
        code = ""
    if not code:
        raise ValueError("No code in HuggingFace response")
    return code

def generate_code_with_llm(brief: str) -> str:
    logger.info("Starting code generation with LLM...")
    logger.info(f"Prompt: {brief}")
    if AIPIPE_API_KEY:
        try:
            code = call_aipipe(brief)
            logger.info("AIPipe response status: 200")
            return code
        except Exception as e:
            logger.warning(f"AIPipe failed: {e}, falling back to HuggingFace")
    else:
        logger.warning("AIPipe API key not configured, using HuggingFace")

    if HUGGINGFACE_API_KEY:
        return call_huggingface(brief)
    else:
        raise Exception("No LLM API keys configured")
