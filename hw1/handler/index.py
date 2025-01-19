import os
import json
import requests
import base64
import subprocess
import re

TG_API_KEY = os.getenv("TG_API_KEY")
YA_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
OCR_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
GET_FILE_PATH_URL_PATTERN = "https://api.telegram.org/bot{}/getFile?file_id={}"
SEND_MSG_URL_PATTERN = "https://api.telegram.org/bot{}/sendMessage"
DOWNLOAD_FILE_URL_PATTERN = "https://api.telegram.org/file/bot{}/"
LOCAL_PATH = "/function/storage/images"
CATALOG = os.getenv("folder_id")
MAX_MESSAGE_LEN = 4096

DEFAULT_ANSWER = """
Я помогу подготовить ответ на экзаменационный вопрос по дисциплине "Операционные системы".

Пришлите мне фотографию с вопросом или наберите его текстом.
                
Примеры: 
1. Управление памятью: Ассоциативная память (TLB).
2. Файловые системы: Операции над файлами.
3. Кооперация процессов: Условия Бернстайна.
4. Управление памятью: Принцип локальности.
"""

predefined_answers = {
    "/help": DEFAULT_ANSWER,
    "/start": DEFAULT_ANSWER,
}


def handler(event, context):
    print("received message")

    req = json.loads(event['body'])
    print(f"req - {req}")
    message = req.get('message', {})
    text = message.get('text', '')
    chat_id = message.get('chat', {}).get('id', 0)
    message_id = message.get('message_id', 0)

    if text:
        if text in predefined_answers:
            send_reply(chat_id, predefined_answers[text], message_id)
            return {"statusCode": 200}

        prompt_result = do_prompt(text)
        send_reply(chat_id, prompt_result, message_id)
        return {"statusCode": 200}

    if not message.get('photo'):
        send_reply(chat_id, "Я могу обработать только текстовое сообщение или фотографию.", message_id)
        return {"statusCode": 200}

    res = process_image(message)
    send_reply(chat_id, res, message_id)

    return {"statusCode": 200}


def process_image(message):
    file_id = message['photo'][-1]['file_id']

    print(f"file_id - {file_id}")

    file_path_resp = get_file_path(file_id)
    print(f"file_path_resp - {file_path_resp}")

    download_path = DOWNLOAD_FILE_URL_PATTERN.format(TG_API_KEY) + file_path_resp['result']['file_path']
    print(f"download_path - {download_path}")

    ocr_text = proceed_ocr(download_path)
    prompt_result = do_prompt(ocr_text)
    print(f"image_text - {prompt_result}")

    return prompt_result


def get_file_path(file_id):
    url = GET_FILE_PATH_URL_PATTERN.format(TG_API_KEY, file_id)
    response = requests.get(url)
    return response.json()


def download_file(filepath, url):
    cmd = ["curl", url, "--output", filepath]
    print(f"cmd - {cmd}")
    subprocess.run(cmd)


def proceed_ocr(file_path):
    response = requests.get(file_path)

    if response.status_code == 200:
        image_data = response.content
    else:
        print("ERROR GET IMAGE")
        raise Exception(f"Error: {response.status_code}")

    print(f"image_data - {image_data}")

    base64_img = base64.b64encode(image_data).decode('utf-8')

    ocr_request = {
        "mimeType": "JPEG",
        "languageCodes": ["ru"],
        "model": "page",
        "content": base64_img
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + get_iam_token(),
        "x-data-logging-enabled": "true"
    }

    response = requests.post(OCR_URL, json=ocr_request, headers=headers)
    ocr_response = response.json()
    print(f"photo text - {ocr_response}")

    if os.path.exists(file_path):
        os.remove(file_path)

    return ocr_response['result']['textAnnotation']['fullText']

def clean_markdown(text):
    text = re.sub(r'([*_]{2})(.*?)\1', r'\2', text)
    text = re.sub(r'([*_])(.*?)\1', r'\2', text)
    text = re.sub(r'```(.*?)```', r'\1', text)
    return text

def send_reply(chat_id, text, reply_to_message_id):
    text = clean_markdown(text)

    text_chunks = [text[i:i + MAX_MESSAGE_LEN] for i in range(0, len(text), MAX_MESSAGE_LEN)]
    print(f"text_chunks{text_chunks}")

    for chunk in text_chunks:
        send_msg_payload = {
            "chat_id": chat_id,
            "text": chunk,
            "reply_to_message_id": reply_to_message_id,
            "parse_mode": "Markdown"
        }
        url = SEND_MSG_URL_PATTERN.format(TG_API_KEY)
        response = requests.post(url, json=send_msg_payload)

        if response.status_code >= 300:
            print(f"Failed to send reply: {response.status_code} {response.text}")


def do_prompt(prompt):
    setup_file_path = os.path.join(LOCAL_PATH, "instruction.txt")

    try:
        with open(setup_file_path, 'r') as f:
            setup_content = f.read()
    except FileNotFoundError:
        setup_content = "Ты преподаватель по предмету \"Операционные системы\" в университете. Ответь на следующие экзаменационные билеты."

    print(f"instructions - {setup_content}")

    request = {
        "modelUri": f"gpt://{CATALOG}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": "1200"
        },
        "messages": [
            {"role": "system", "text": setup_content},
            {"role": "user", "text": prompt}
        ]
    }

    iam_token = get_iam_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + iam_token
    }

    response = requests.post(YA_GPT_URL, json=request, headers=headers)
    response_data = response.json()

    print(f"Prompt - {response_data}")
    if len(response_data['result']['alternatives']) == 0:
        return "Нет ответа"

    return response_data['result']['alternatives'][0]['message']['text']


def get_iam_token():
    metadata_url = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    headers = {
        "Metadata-Flavor": "Google"
    }
    response = requests.get(metadata_url, headers=headers)
    token_data = response.json()
    return token_data['access_token']
