terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

locals {
  key_dir = "~"
}


provider "yandex" {
  cloud_id                 = var.cloud_id
  folder_id                = var.folder_id
  service_account_key_file = "${local.key_dir}/.yc-keys/key.json"
  zone                     = var.zone
}


resource "yandex_vpc_network" "network" {
  name = "vvot16-network"
}

resource "yandex_vpc_subnet" "subnet" {
  name       = "vvot16-subnet"
  zone       = var.zone
  v4_cidr_blocks = ["192.168.10.0/24"]
  network_id = yandex_vpc_network.network.id
}


data "yandex_compute_image" "ubuntu" {
  family = "ubuntu-2404-lts-oslogin"
}

resource "yandex_compute_disk" "boot-disk" {
  name     = "vvot16-boot-disk"
  type     = "network-ssd"
  image_id = data.yandex_compute_image.ubuntu.id
  size     = 20
}

resource "yandex_compute_instance" "server" {
  name        = "vvot16-web-server"
  platform_id = "standard-v3"
  hostname    = "web"

  resources {
    core_fraction = 20
    cores         = 2
    memory        = 1
  }

  boot_disk {
    disk_id = yandex_compute_disk.boot-disk.id
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.subnet.id
    nat       = true
  }

  metadata = {
    ssh-keys = "ubuntu:${file("~/.ssh/id_rsa.pub")}"
  }
}

output "web-server-ip" {
  value = yandex_compute_instance.server.network_interface[0].nat_ip_address
}


variable "cloud_id" {
  type        = string
  description = "ID облака"
}

variable "folder_id" {
  type        = string
  description = "ID каталога"
}

variable "zone" {
  type        = string
  description = "Yandex Cloud Зона"
  default     = "ru-central1-d"
}