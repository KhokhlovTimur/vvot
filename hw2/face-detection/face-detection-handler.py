import os
import json
import cv2
import boto3

data_dir = "images"
gw_image_pattern = "https://%s/?image=%s"
img_dir = "/function/storage/images"


def handler(event, req):
    print("face-detection")
    print(f"event - {event}")
    messages_data = event
    messages = messages_data.get("messages", [])
    print(f"messages - {messages}")

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")

    for message in messages:
        image_path = os.path.join(img_dir, message["details"]["object_id"])

        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"Failed to read image: {image_path}")

        max_width = 1920
        max_height = 1080

        original_height, original_width = img.shape[:2]
        if original_width > max_width or original_height > max_height:
            scaling_factor = min(max_width / original_width, max_height / original_height)
            img = cv2.resize(img, None, fx=scaling_factor, fy=scaling_factor, interpolation=cv2.INTER_AREA)
            additional_scaling_factor = 0.90
            new_width = int(img.shape[1] * additional_scaling_factor)
            new_height = int(img.shape[0] * additional_scaling_factor)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

        resized_height, resized_width = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        #blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=6, minSize=(30, 30))

        print(f"faces - {faces}")

        for (x, y, w, h) in faces:
            x_original = int(x * (original_width / resized_width))
            y_original = int(y * (original_height / resized_height))
            w_original = int(w * (original_width / resized_width))
            h_original = int(h * (original_height / resized_height))

            bounds = {
                "x": x_original,
                "y": y_original,
                "width": w_original,
                "height": h_original
            }

            task = {
                "bounds": bounds,
                "object_id": message["details"]["object_id"]
            }

            print(f"new task - {task}")

            session = boto3.session.Session()
            sqs_client = session.client(
                'sqs',
                region_name='ru-central1',
                endpoint_url='https://message-queue.api.cloud.yandex.net',
                aws_access_key_id=os.getenv('ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('SECRET_ACCESS_KEY')
            )

            queue_url = os.getenv("QUEUE_URL")

            sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(task)
            )

    return {"statusCode": 200}
