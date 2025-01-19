terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

resource "yandex_iam_service_account" "func-bot-account-kte" {
  name        = "func-bot-account-kte"
  description = "Аккаунт для функции вебхука"
  folder_id   = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_binding" "mount-iam" {
  folder_id = var.folder_id
  role      = "storage.admin"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte.id}",
  ]
}

resource "yandex_resourcemanager_folder_iam_binding" "ocr-iam" {
  folder_id = var.folder_id
  role      = "ai.vision.user"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte.id}",
  ]
}

resource "yandex_resourcemanager_folder_iam_binding" "yagpt-iam" {
  folder_id = var.folder_id
  role      = "ai.languageModels.user"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte.id}",
  ]
}

provider "yandex" {
  cloud_id                 = var.cloud_id
  folder_id                = var.folder_id
  service_account_key_file = "../../../terraform/.yc-keys/key.json"
}

resource "yandex_storage_bucket" "mount-bucket" {
  bucket    = "khokhlovte-ocr-bot-mount"
  folder_id = var.folder_id
}


resource "yandex_function" "handler_func" {
  name               = "func-bot"
  user_hash          = archive_file.zip.output_sha256
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = 128
  execution_timeout  = 20
  service_account_id = yandex_iam_service_account.func-bot-account-kte.id

  environment = {
    "TG_API_KEY"    = var.TG_API_KEY,
    "IMAGES_BUCKET" = yandex_storage_bucket.mount-bucket.bucket,
    "folder_id"     = var.folder_id
  }

  storage_mounts {
    mount_point_name = "images"
    bucket           = yandex_storage_bucket.mount-bucket.bucket
    prefix           = ""
  }

  content {
    zip_filename = archive_file.zip.output_path
  }
}

output "func_url" {
  value = "https://functions.yandexcloud.net/${yandex_function.handler_func.id}"
}

resource "archive_file" "zip" {
  type        = "zip"
  output_path = "src.zip"
  source_file = "./handler/index.py"
}


resource "yandex_storage_object" "yagpt_setup" {
  bucket = yandex_storage_bucket.mount-bucket.id
  key    = "instruction.txt"
  source = "./instruction.txt"
}

resource "yandex_function_iam_binding" "function-iam" {
  function_id = yandex_function.handler_func.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}


resource "null_resource" "triggers" {
  triggers = {
    api_key = var.TG_API_KEY
  }

  provisioner "local-exec" {
    command = "curl --insecure -X POST https://api.telegram.org/bot${var.TG_API_KEY}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.handler_func.id}"
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