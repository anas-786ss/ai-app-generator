from pydantic import BaseModel
from typing import List, Optional

class Attachment(BaseModel):
    filename: str
    content_base64: str

class GenerateRequest(BaseModel):
    email: str
    secret: str
    task: str
    round: int
    nonce: str
    brief: str
    checks: List[str]
    evaluation_url: str
    attachments: List[Attachment] = []
