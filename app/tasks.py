import os
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

def save_attachments(attachments: list):
    filenames = []
    for att in attachments:
        try:
            filename = att.filename.replace("/", "_").replace("\\", "_")  # Sanitize
            file_path = UPLOAD_FOLDER / filename
            content = base64.b64decode(att.content_base64)
            with open(file_path, "wb") as f:
                f.write(content)
            filenames.append(str(file_path))
            logger.info(f"Saved attachment {filename}")
        except Exception as e:
            logger.warning(f"Failed to save attachment {att.filename}: {e}")
    return filenames
