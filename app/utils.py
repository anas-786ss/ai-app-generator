import logging
import os
from python_json_logger import json_logger

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = json_logger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        extra={'log_file': '/tmp/app_logs.json'}
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("File logging initialized")
    return logger

def log_request(request: dict):
    logger = logging.getLogger()
    logger.info("Received request", extra={"request": request})
