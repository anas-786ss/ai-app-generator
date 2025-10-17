import os
import httpx
from app.utils import setup_logging

logger = setup_logging()

async def generate_code(brief: str, attachment_paths: list) -> str:
    try:
        api_key = os.getenv("AIPIPE_API_KEY") or os.getenv("HUGGINGFACE_API_KEY")
        if not api_key:
            logger.warning("No AI API key provided, using dummy response")
            return """
<!DOCTYPE html>
<html>
<head>
    <title>Captcha Solver</title>
</head>
<body>
    <h1>Captcha Solver</h1>
    <img src="{}" alt="Captcha">
    <p>Solved: Dummy Response</p>
</body>
</html>
""".format(attachment_paths[0] if attachment_paths else "https://example.com/image.png")
        
        endpoint = "https://api-inference.huggingface.co/models/gpt2"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "inputs": f"Generate HTML code for a captcha solver based on this brief: {brief}",
            "parameters": {"max_length": 500}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            generated = response.json()[0]["generated_text"]
            logger.info("Code generated successfully")
            return generated
    except Exception as e:
        logger.error(f"Error generating code: {str(e)}")
        raise
