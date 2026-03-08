#!/bin/bash
#---------------------------------------------------------------------
# Install script for Log_esphome_web on Debian/Ubuntu
# https://github.com/shmvme-cmd/Log_esphome_web
#---------------------------------------------------------------------

set -e

REPO="https://github.com/shmvme-cmd/Log_esphome_web"
ARCHIVE_URL="${REPO}/archive/refs/heads/main.tar.gz"
ARCHIVE_NAME="Log_esphome_web-main"
PROJECT_DIR="/usr/bin/log-esphome-web"
SERVICE_NAME="log-esphome-web"
SERVICE_USER="root"
PORT=8000

# ── Root check ────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    echo "Этот скрипт должен запускаться от root (sudo bash install.sh)"
    exit 1
fi

# ── 1. Системные зависимости ──────────────────────────────────
echo ">>> [1/6] Установка системных зависимостей..."
apt-get update -qq
apt-get install -y --no-install-recommends curl wget ca-certificates

# ── 2. Установка uv ──────────────────────────────────────────
echo ">>> [2/6] Установка uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' /root/.bashrc 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> /root/.bashrc
    fi
else
    echo "uv уже установлен: $(uv --version)"
fi

UV_BIN="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"

if ! "$UV_BIN" --version &>/dev/null; then
    echo "Ошибка: uv не найден после установки."
    exit 1
fi
echo "uv: $("$UV_BIN" --version)"

# ── 3. Загрузка проекта ───────────────────────────────────────
echo ">>> [3/6] Загрузка проекта..."
cd /tmp
rm -rf "${ARCHIVE_NAME}" log-esphome-web.tar.gz
wget -q "${ARCHIVE_URL}" -O log-esphome-web.tar.gz
tar xfz log-esphome-web.tar.gz

# ── 4. Копирование файлов ─────────────────────────────────────
echo ">>> [4/6] Установка файлов в ${PROJECT_DIR}..."
rm -rf "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"
cp -r "/tmp/${ARCHIVE_NAME}/." "${PROJECT_DIR}/"

# ── 5. Создание venv и установка зависимостей ─────────────────
echo ">>> [5/6] Установка зависимостей Python..."
cd "${PROJECT_DIR}"
"$UV_BIN" venv
"$UV_BIN" pip install -e .

# Создать директорию для БД
mkdir -p "${PROJECT_DIR}/data"

# ── 6. Systemd-сервис ─────────────────────────────────────────
echo ">>> [6/6] Создание systemd-сервиса ${SERVICE_NAME}..."

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=ESPHome PID Logger — Web Interface
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="HOME=${HOME}"
ExecStart=${UV_BIN} run ${PROJECT_DIR}/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

# ── Проверка ─────────────────────────────────────────────────
sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo ""
    echo "========================================"
    echo " Установка завершена успешно!"
    echo " Веб-интерфейс: http://$(hostname -I | awk '{print $1}'):${PORT}"
    echo " Управление сервисом:"
    echo "   systemctl status ${SERVICE_NAME}"
    echo "   systemctl restart ${SERVICE_NAME}"
    echo "   journalctl -u ${SERVICE_NAME} -f"
    echo "========================================"
    # Очистка временных файлов
    rm -rf "/tmp/${ARCHIVE_NAME}" "/tmp/log-esphome-web.tar.gz"
else
    echo ""
    echo "Ошибка: сервис не запустился."
    echo "Проверьте журнал: journalctl -u ${SERVICE_NAME} -b --no-pager"
    exit 1
fi
