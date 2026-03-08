# ESPHome PID Logger — Web Interface

Веб-приложение для мониторинга логов PID Autotune с ESPHome-устройств. Подключается к устройству через native API, отображает логи в реальном времени, сохраняет результаты Autotune в базу данных и позволяет управлять кнопками устройства.

## Возможности

- **Подключение к ESPHome** через native API (шифрование Noise PSK)
- **Сканирование сети** — автоматический поиск ESPHome-устройств через mDNS
- **Лог в реальном времени** — вывод PID Autotune сообщений в браузерный терминал
- **Запуск Autotune** — выбор кнопки из списка сущностей устройства и отправка команды
- **База данных** — сохранение API ключей устройств и результатов Autotune в SQLite
- **История результатов** — просмотр, фильтрация и детальный анализ результатов по устройствам
- **Экспорт в JSON** — выгрузка логов текущей сессии

## Стек технологий

| Компонент | Версия |
|---|---|
| Python | ≥ 3.12 |
| Flask | ≥ 3.0 |
| Flask-SocketIO | ≥ 5.3.6 |
| aioesphomeapi | ≥ 43.10.1 |
| zeroconf | ≥ 0.148.0 |
| SQLite | stdlib |

## Установка на Debian / Ubuntu

```bash
wget -qO install.sh https://raw.githubusercontent.com/shmvme-cmd/Log_esphome_web/main/install.sh
sudo bash install.sh
```

Скрипт автоматически:
1. Устанавливает менеджер пакетов [`uv`](https://docs.astral.sh/uv/)
2. Скачивает проект из GitHub
3. Создаёт виртуальное окружение и устанавливает зависимости
4. Регистрирует и запускает systemd-сервис `log-esphome-web`

После установки веб-интерфейс доступен по адресу: `http://<IP_сервера>:8000`

## Управление сервисом

```bash
# Статус
systemctl status log-esphome-web

# Перезапуск
systemctl restart log-esphome-web

# Логи в реальном времени
journalctl -u log-esphome-web -f

# Остановка
systemctl stop log-esphome-web
```

## Ручной запуск (для разработки)

```bash
# Клонировать репозиторий
git clone https://github.com/shmvme-cmd/Log_esphome_web.git
cd Log_esphome_web

# Создать venv и установить зависимости (требуется uv)
uv venv
uv pip install -e .

# Запустить
.venv/bin/python main.py
# или
uv run main.py
```

Приложение запустится на `http://0.0.0.0:8000`.

## Структура проекта

```
Log_esphome_web/
├── main.py                 # Точка входа
├── pyproject.toml          # Зависимости проекта
├── install.sh              # Скрипт установки на Debian/Ubuntu
├── app/
│   ├── __init__.py         # Application Factory (Flask)
│   ├── routes.py           # HTTP-маршруты (/, /scan_mdns, /get_json)
│   ├── sockets.py          # Socket.IO события + ESPHome клиент
│   ├── api.py              # REST API (/api/devices, /api/results)
│   └── db.py               # SQLite слой данных
├── templates/
│   └── index.html          # SPA интерфейс
├── static/
│   ├── css/style.css       # Тёмная тема
│   └── js/app.js           # Клиентская логика (Socket.IO)
└── data/
    └── esphome.db          # SQLite база данных (создаётся автоматически)
```

## Настройка ESPHome

В YAML-конфигурации устройства должен быть включён native API с шифрованием:

```yaml
api:
  encryption:
    key: "ваш_base64_ключ"
```

Ключ шифрования вводится в поле **API Key** в веб-интерфейсе при подключении.

## REST API

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/devices` | Список сохранённых устройств |
| POST | `/api/devices` | Добавить устройство `{name, ip, api_key}` |
| GET | `/api/devices/<id>` | Получить устройство по ID |
| DELETE | `/api/devices/<id>` | Удалить устройство |
| GET | `/api/results` | История результатов Autotune |
| GET | `/api/results?device_id=1` | Фильтр по устройству |
| GET | `/api/results?device_ip=...` | Фильтр по IP |
| GET | `/api/results/ips` | Список IP с результатами |
| GET | `/api/results/<id>` | Результат по ID |
| DELETE | `/api/results/<id>` | Удалить результат |

## Лицензия

MIT
