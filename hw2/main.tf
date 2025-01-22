terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  cloud_id                 = var.cloud_id
  folder_id                = var.folder_id
  service_account_key_file = "../../../terraform/.yc-keys/key.json"
}

resource "yandex_iam_service_account" "func-bot-account-kte-faces" {
  name        = "func-bot-account-kte-faces"
  description = "Аккаунт для взаимодействия"
  folder_id   = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_binding" "ocr-iam" {
  folder_id = var.folder_id
  role      = "editor"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte-faces.id}",
  ]
}


resource "yandex_storage_bucket" "bucket-photos" {
  bucket    = "vvot16-photos"
  folder_id = var.folder_id
}

resource "yandex_storage_bucket" "bucket-faces" {
  bucket    = "vvot16-faces"
  folder_id = var.folder_id
}


resource "yandex_function" "face-detection-handler" {
  name              = "vvot16-face-detection"
  user_hash         = archive_file.face-detection-handler-zip.output_base64sha256
  runtime           = "python312"
  entrypoint        = "face-detection-handler.handler"
  memory            = 128
  execution_timeout = 20
  service_account_id = yandex_iam_service_account.func-bot-account-kte-faces.id

  environment = {
    "QUEUE_URL"             = yandex_message_queue.task_queue.id,
    "AWS_ACCESS_KEY_ID"     = yandex_iam_service_account_static_access_key.queue-static-key.access_key
    "AWS_SECRET_ACCESS_KEY" = yandex_iam_service_account_static_access_key.queue-static-key.secret_key,
  }

  storage_mounts {
    mount_point_name = "images"
    bucket           = yandex_storage_bucket.bucket-photos.bucket
    prefix           = ""
  }

  content {
    zip_filename = archive_file.face-detection-handler-zip.output_path
  }
}

resource "archive_file" "face-detection-handler-zip" {
  type        = "zip"
  output_path = "face-detection-handler.zip"
  source_file = "./handlers/face-detection-handler.py"
}


resource "yandex_function_trigger" "face-detection-handler_trigger" {
  name        = "vvot16-photos-trigger"
  description = "Триггер для запуска обработчика face-detection-handler"

  function {
    id                 = yandex_function.face-detection-handler.id
    service_account_id = yandex_iam_service_account.func-bot-account-kte-faces.id
    retry_attempts     = 2
    retry_interval     = 10
  }

  object_storage {
    bucket_id    = yandex_storage_bucket.bucket-photos.id
    suffix       = ".jpg"
    create       = true
    update       = false
    delete       = false
    batch_cutoff = 2
  }
}


resource "yandex_function" "face-cut-handler" {
  name              = "vvot16-face-cut"
  user_hash         = archive_file.face-cut-handler-zip.output_sha256
  runtime           = "python312"
  entrypoint        = "face-cut-handler.handler"
  memory            = 128
  execution_timeout = 20
  service_account_id = yandex_iam_service_account.func-bot-account-kte-faces.id

  environment = {
    "AWS_ACCESS_KEY_ID"     = yandex_iam_service_account_static_access_key.queue-static-key.access_key
    "AWS_SECRET_ACCESS_KEY" = yandex_iam_service_account_static_access_key.queue-static-key.secret_key
  }

  storage_mounts {
    mount_point_name = "images"
    bucket           = yandex_storage_bucket.bucket-photos.bucket
    prefix           = ""
  }

  storage_mounts {
    mount_point_name = "faces"
    bucket           = yandex_storage_bucket.bucket-faces.bucket
    prefix           = ""
  }

  content {
    zip_filename = archive_file.face-cut-handler-zip.output_path
  }
}

resource "archive_file" "face-cut-handler-zip" {
  type        = "zip"
  output_path = "faces-src.zip"
  source_dir  = "handlers/face-cut-handler.py"
}


resource "yandex_function" "tg-bot-handler" {
  name              = "vvot16-boot"
  user_hash         = archive_file.tg-bot-handler-zip.output_sha256
  runtime           = "python312"
  entrypoint        = "tg-bot-handler.handler"
  memory            = 128
  execution_timeout = 20
  environment = {
    "TG_API_KEY" = var.TG_API_KEY
  }
  service_account_id = yandex_iam_service_account.func-bot-account-kte-faces.id

  storage_mounts {
    mount_point_name = "faces"
    bucket           = yandex_storage_bucket.bucket-faces.bucket
    prefix           = ""
  }

  storage_mounts {
    mount_point_name = "images"
    bucket           = yandex_storage_bucket.bucket-photos.bucket
    prefix           = ""
  }

  content {
    zip_filename = archive_file.tg-bot-handler-zip.output_path
  }
}

resource "archive_file" "tg-bot-handler-zip" {
  type        = "zip"
  output_path = "bot_src.zip"
  source_dir  = "./handlers/tg-bot-handler.py"
}

resource "yandex_function_iam_binding" "function-iam" {
  function_id = yandex_function.tg-bot-handler.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}


resource "yandex_iam_service_account_static_access_key" "queue-static-key" {
  service_account_id = yandex_iam_service_account.func-bot-account-kte-faces.id
  description        = "Ключ для очереди"
}

resource "yandex_message_queue" "task_queue" {
  name                       = "vvot16-task"
  access_key                 = yandex_iam_service_account_static_access_key.queue-static-key.access_key
  secret_key                 = yandex_iam_service_account_static_access_key.queue-static-key.secret_key
  visibility_timeout_seconds = 600
  receive_wait_time_seconds  = 20
  message_retention_seconds  = 1209600
}


resource "yandex_ydb_database_serverless" "images-db" {
  name                = "vvot16-images-db"
  deletion_protection = false
  serverless_database {
    enable_throttling_rcu_limit = false
    provisioned_rcu_limit       = 10
    storage_size_limit          = 50
    throttling_rcu_limit        = 0
  }
}

resource "yandex_ydb_table" "image-face" {
  path              = "image-face"
  connection_string = yandex_ydb_database_serverless.images-db.ydb_full_endpoint

  column {
    name     = "ImageId"
    type     = "String"
    not_null = true
  }
  column {
    name     = "FaceId"
    type     = "String"
    not_null = true
  }
  column {
    name     = "FaceName"
    type     = "String"
    not_null = false
  }

  primary_key = ["FaceId"]
}


resource "null_resource" "triggers" {
  triggers = {
    api_key = var.TG_API_KEY
  }

  provisioner "local-exec" {
    command = "curl --insecure -X POST https://api.telegram.org/bot${var.TG_API_KEY}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.tg-bot-handler.id}"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "curl --insecure -X POST https://api.telegram.org/bot${self.triggers.api_key}/deleteWebhook"
  }
}


variable "TG_API_KEY" {
  type        = string
  description = "Ключ тг бота"
}

variable "cloud_id" {
  type        = string
  description = "ID облака"
}

variable "folder_id" {
  type        = string
  description = "ID каталога"
}