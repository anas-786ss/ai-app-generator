# app/utils.py
import logging
import sys
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler with JSON format
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
        rename_fields={'levelname': 'severity', 'asctime': 'timestamp'}
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler for persistent logs
    file_handler = logging.FileHandler('app_logs.json')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def log_request(data: dict):
    with open("requests_log.json", "a") as f:
        log_entry = {"time": str(datetime.now()), "data": data}
        f.write(json.dumps(log_entry) + "\n")
