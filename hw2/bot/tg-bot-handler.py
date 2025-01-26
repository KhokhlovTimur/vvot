import os
import json
import requests
from ydb import Driver, TableClient
import ydb
from typing import List, Dict, Any

# Processing = 1 - фото в обработке

YDB_URL = os.getenv("YDB_URL")
TG_API_KEY = os.getenv("TG_API_KEY")
API_GW_URL = os.getenv("API_GW_URL")
OCR_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
MAX_MESSAGE_LEN = 4096
GW_PATTERN = "https://{}/?face={}"
GW_IMAGE_PATTERN = "https://{}/?image={}"
SEND_MSG_URL_PATTERN = "https://api.telegram.org/bot{}/sendMessage"
SEND_PHOTO_URL_PATTERN = "https://api.telegram.org/bot{}/sendPhoto"


def handler(event: Dict[str, Any], context: Any):
    print("Received message")

    req = json.loads(event['body'])
    print(f"req - {req}")
    update_id = req.get('update_id')
    message_data = req.get('message')
    print(message_data)
    if not message_data:
        return  {"statusCode": 200}

    message = {
        "message_id": message_data['message_id'],
        "chat_id": message_data['chat']['id'],
        "text": message_data.get('text', '')
    }

    ydb_url = "grpcs://" + os.getenv("YDB_URL")
    db = Driver(endpoint=ydb_url, database=os.getenv("YDB_ENDPOINT"), credentials=ydb.iam.MetadataUrlCredentials())
    db.wait(fail_fast=True, timeout=30)
    table_client = TableClient(db)
    session = table_client.session().create()

    if message['text'] and not message['text'].startswith('/'):
        print("save face name")
        try:
            save_name_to_db(session, get_processing_face_id(session), message['text'])
        except Exception as e:
            send_reply(message['chat_id'], "Ошибка. Не было выбрано лицо для обработки", message['message_id'])
        send_reply(message['chat_id'], f"Название для лица сохранено - <{message['text']}>", message['message_id'])

    if message['text'].startswith('/') and (message['text'] != '/getface' and not message['text'].startswith('/find')):
        send_reply(message['chat_id'], f"Ошибка. Команды {message['text']} не существует.", message['message_id'])

    if message['text'].startswith('/getface'):
        try:
            face_id = get_face_id(session)
            print(f"face id - {face_id}")
            face_url = GW_PATTERN.format(API_GW_URL, face_id)
            print(f"face url - {face_url}")
            send_photo(message['chat_id'], face_url)
            set_processing_status(session, face_id, '1')
        except Exception as e:
            print(f"Error handling /getface: {str(e)}")
            send_reply(message['chat_id'], "Не удалось найти фото без имени", message['message_id'])

        return {"statusCode": 200}

    if message['text'].startswith('/find'):
        text_parts = message['text'].strip().split(" ")
        name = " ".join(text_parts[1:]) if len(text_parts) > 1 else ""
        if name:
            try:
                images = find_by_name(session, name)
                if images:
                    for image in images:
                        image_url = GW_IMAGE_PATTERN.format(API_GW_URL, image)
                        send_photo(message['chat_id'], image_url)
                else:
                    send_reply(message['chat_id'], f"Фотографии с именем <{name}> не найдены", message['message_id'])
            except Exception as e:
                print(f"Error handling /find: {str(e)}")
                send_reply(message['chat_id'], "Ошибка при поиске", message['message_id'])
            return {"statusCode": 200}

    return {"statusCode": 200}


def send_reply(chat_id: int, text: str, reply_to_msg_id: int) -> None:
    if len(text) > MAX_MESSAGE_LEN:
        texts = [text[:MAX_MESSAGE_LEN], text[MAX_MESSAGE_LEN:]]
    else:
        texts = [text]

    for text in texts:
        send_msg_req = {
            "chat_id": chat_id,
            "text": text,
            "reply_to_message_id": reply_to_msg_id,
            "parse_mode": "Markdown"
        }
        response = requests.post(
            SEND_MSG_URL_PATTERN.format(TG_API_KEY),
            json=send_msg_req
        )
        if response.status_code >= 300:
            print(f"Failed to send reply: {response.status_code} {response.text}")


def send_photo(chat_id: int, photo_url: str) -> None:
    send_photo_req = {
        "chat_id": chat_id,
        "photo": photo_url
    }
    response = requests.post(
        SEND_PHOTO_URL_PATTERN.format(TG_API_KEY),
        json=send_photo_req
    )
    if response.status_code >= 300:
        print(f"Failed to send photo: {response.status_code} {response.text}")


def get_face_id(session) -> str:
    print("In get face id")
    res = fetch_db_q(session.transaction().execute(
        "SELECT FaceId FROM image_face WHERE FaceName IS NULL AND Processing = '1' LIMIT 1"))
    print(f"without name - {res}")
    if res:
        face_id = res[0]["FaceId"].decode("utf-8")
        print(f"already processing id - {face_id}")
        return face_id
    else:
        res = fetch_db_q(session.transaction().execute("SELECT FaceId FROM image_face WHERE FaceName IS NULL LIMIT 1"))
        print(f"face id res - {res}")
        face_id = res[0]["FaceId"].decode("utf-8")
        print(f"without name not processing - {face_id}")
        return face_id


def get_processing_face_id(session):
    print("In get last face id")
    res = fetch_db_q(session.transaction().execute(
        "SELECT FaceId FROM image_face WHERE FaceName IS NULL AND Processing = '1' LIMIT 1"))
    print(f"without name - {res}")
    if res:
        face_id = res[0]["FaceId"].decode("utf-8")
        set_processing_status(session, face_id, '0')
        return face_id
    else:
        raise Exception("Не было выбрано лицо для обработки")


def find_by_name(session, name: str) -> List[str]:
    res = fetch_db_q(session.transaction().execute(f"SELECT ImageId FROM image_face WHERE FaceName = '{name}'"))
    print(f"find with names - {res}")
    return [row['ImageId'].decode("utf-8") for row in res] if res else []


def save_name_to_db(session, face_id, text):
    session.transaction().execute(f"UPDATE image_face SET FaceName='{text}'WHERE FaceId='{face_id}'", commit_tx=True)
    print(f"Face name {face_id}: {text}")


def set_processing_status(session, face_id, status):
    q = f"UPDATE image_face SET Processing='{status}' WHERE FaceId='{face_id}'"
    print(q)
    session.transaction().execute(q, commit_tx=True)
    print(f"Set processing status for {face_id} - {status}")


def fetch_db_q(res):
    return res[0].rows
