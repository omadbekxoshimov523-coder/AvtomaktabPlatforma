#!/usr/bin/env bash
# EC2 instansiyasini tayyorlaydi (Ubuntu / Amazon Linux).
# Ishlatish:  bash scripts/aws_bootstrap.sh web   |   bash scripts/aws_bootstrap.sh bot
set -euo pipefail

ROLE="${1:-}"
if [ "$ROLE" != "web" ] && [ "$ROLE" != "bot" ]; then
    echo "Foydalanish: bash scripts/aws_bootstrap.sh web|bot" >&2
    exit 2
fi

echo "=== [$ROLE] bootstrap boshlandi ==="

if [ "$(id -u)" -ne 0 ]; then
    sudo -v
    SUDO="sudo"
else
    SUDO=""
fi

if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -y
    DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y \
        docker.io docker-compose-plugin git ca-certificates curl nginx
elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y docker git ca-certificates curl nginx
elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y docker git ca-certificates curl nginx
else
    echo "XATO: paket menejeri (apt/dnf/yum) topilmadi" >&2
    exit 1
fi

$SUDO systemctl enable --now docker

# Ba'zi AMI'larda docker compose plugin yo'q — o'rnatamiz
if ! docker compose version >/dev/null 2>&1; then
    $SUDO mkdir -p /usr/local/lib/docker/cli-plugins
    $SUDO curl -fsSL \
        "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    $SUDO chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

if [ "$ROLE" = "web" ]; then
    $SUDO systemctl enable --now nginx
    $SUDO mkdir -p /var/www/autoprime /opt/avtomaktab/backups
else
    $SUDO mkdir -p /opt/autoprime-bot
fi

echo "=== [$ROLE] bootstrap tugadi ==="
docker --version
docker compose version
