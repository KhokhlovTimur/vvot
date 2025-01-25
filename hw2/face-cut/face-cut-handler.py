import os
import json
import uuid
import logging
from PIL import Image
import ydb
from ydb import Driver, TableClient

INPUT_DIR = "/function/storage/images"
OUTPUT_DIR = "/function/storage/faces"

logging.basicConfig(level=logging.INFO)


def open_db():
    ydb_url = "grpcs://" + os.getenv("YDB_URL")
    driver = Driver(endpoint=ydb_url, database=os.getenv("YDB_ENDPOINT"), credentials=ydb.iam.MetadataUrlCredentials())
    driver.wait(fail_fast=True, timeout=30)
    return driver


def save_face_to_db(session, face_id, object_id):
    relations_path = "image_face"
    print(f"obj_id - {object_id}")
    print(f"face_id - {face_id}")

    session.transaction().execute(
        f"INSERT INTO {relations_path} (ImageId, FaceId) VALUES ('{object_id}', '{face_id}');",
        commit_tx=True
    )


def process_task(session, task):
    img_path = os.path.join(INPUT_DIR, task["object_id"])
    print(f"img_path - {img_path}")
    try:
        img = Image.open(img_path)

    except Exception as e:
        raise RuntimeError(f"Failed to open image {img_path}: {e}")

    bounds = task["bounds"]
    cropped_img = img.crop((
        bounds["x"], bounds["y"],
        bounds["x"] + bounds["width"],
        bounds["y"] + bounds["height"]
    ))

    print(f"cropped_img - {cropped_img}")

    face_id = f"{uuid.uuid4()}.jpg"
    face_path = os.path.join(OUTPUT_DIR, face_id)
    print(f"new face path - {face_path}")

    cropped_img.save(face_path)

    save_face_to_db(session, face_id, task["object_id"])


def handler(request, context):
    print("face-cut-handler")

    print(f"req - {request}")
    messages = request
    print(f"messages - {messages}")

    driver = open_db()
    table_client = TableClient(driver)

    session = table_client.session().create()
    for msg in messages.get("messages", []):
        row_task = msg["details"]["message"]["body"]
        task = json.loads(row_task)
        print(f"task - {task}")

        logging.info(f"Processing task: {task}")
        process_task(session, task)

    return {
        "statusCode": 200,
        "body": "Processing completed successfully"
    }
