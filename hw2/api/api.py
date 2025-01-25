import os
import json
import logging
import base64
from pathlib import Path
from typing import Dict, Any

FACES_DIR = "/function/storage/faces"
IMAGES_DIR = "/function/storage/images"

def handler(event: Dict[str, Any], context: Any):
    name = event.get("queryStringParameters", {}).get("face")
    fdir = FACES_DIR

    if not name:
        name = event.get("queryStringParameters", {}).get("image")
        fdir = IMAGES_DIR

    if not name:
        return {
            "statusCode": 404,
            "body": "Not Found"
        }

    print(f"HTTP Method: {event['httpMethod']}, File: {name}")

    file_path = Path(fdir) / name
    if not file_path.exists():
        return {
            "statusCode": 404,
            "body": "File Not Found"
        }

    try:
        with open(file_path, "rb") as file:
            file_bytes = file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return {
            "statusCode": 500,
            "body": "Internal Server Error"
        }

    return {
        "statusCode": 200,
        "body": base64.b64encode(file_bytes).decode("utf-8"),
        "headers": {"Content-Type": "image/jpeg"},
        "isBase64Encoded": True
    }