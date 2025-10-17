import os
import base64
from app.utils import setup_logging

logger = setup_logging()

def save_attachments(attachments: list) -> list:
    try:
        paths = []
        for attachment in attachments:
            file_path = f"/tmp/uploads/{attachment.filename}"
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(attachment.content_base64))
            paths.append(file_path)
            logger.info(f"Saved attachment: {file_path}")
        return paths
    except Exception as e:
        logger.error(f"Error saving attachments: {str(e)}")
        raise
