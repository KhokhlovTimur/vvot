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

resource "yandex_resourcemanager_folder_iam_binding" "mount-iam" {
  folder_id = var.folder_id
  role      = "storage.admin"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte-faces.id}",
  ]
}

resource "yandex_resourcemanager_folder_iam_binding" "ocr-iam" {
  folder_id = var.folder_id
  role      = "editor"

  members = [
    "serviceAccount:${yandex_iam_service_account.func-bot-account-kte-faces.id}",
  ]
}


resource "yandex_storage_bucket" "mount-bucket" {
  bucket    = "khokhlovte-ocr-bot-mount"
  folder_id = var.folder_id
}

resource "archive_file" "zip" {
  type        = "zip"
  output_path = "src.zip"
  source_file = "./handler/index.py"
}

resource "null_resource" "triggers" {
  triggers = {
    api_key = var.TG_API_KEY
  }

  provisioner "local-exec" {
    # command = "curl --insecure -X POST https://api.telegram.org/bot${var.TG_API_KEY}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.handler_func.id}"
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