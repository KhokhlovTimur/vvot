terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}


provider "yandex" {
  cloud_id = var.cloud_id
  folder_id = var.folder_id
  service_account_key_file = "../../.yc-keys/key.json"
}

resource "yandex_iam_service_account" "bot_acc" {
  name        = "func-bot-account"
  description = "Аккаунт для функции с ботом"
  folder_id   = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_binding" "mount-iam" {
  folder_id = var.folder_id
  role      = "storage.admin"

  members = [
    "serviceAccount:${yandex_iam_service_account.bot_acc.id}",
  ]
}

resource "yandex_storage_bucket" "mount-bucket" {
  bucket = "khoklovte-ocr-bot-mount"
  folder_id = var.folder_id
}


resource "yandex_resourcemanager_folder_iam_binding" "ocr-iam" {
  folder_id = var.folder_id
  role      = "ai.vision.user"

  members = [
    "serviceAccount:${yandex_iam_service_account.bot_acc.id}",
  ]
}

resource "yandex_resourcemanager_folder_iam_binding" "yagpt-iam" {
  folder_id = var.folder_id
  role      = "ai.languageModels.user"

  members = [
    "serviceAccount:${yandex_iam_service_account.bot_acc.id}",
  ]
}

resource "yandex_resourcemanager_folder_iam_binding" "func-admin-iam" {
  folder_id = var.folder_id
  role      = "serverless.functions.admin"

  members = [
    "serviceAccount:${yandex_iam_service_account.bot_acc.id}",
  ]
}


variable "TG_API_KEY" {
  type = string
  description = "Ключ тг бота"
}

variable "cloud_id" {
  type = string
  description = "ID облака"
}

variable "folder_id" {
  type = string
  description = "ID каталога"
}