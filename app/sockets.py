import asyncio
import logging
import re
import threading
from datetime import datetime

from aioesphomeapi import APIClient, ButtonInfo
from flask import request
from flask_socketio import emit

from . import socketio

logger = logging.getLogger(__name__)

shared_logs: list[dict] = []
_active_sessions: dict[str, dict] = {}



@socketio.on("connect")
def on_connect():
    logger.info("Client connected: %s", request.sid)
    emit("status", {"message": "Соединение установлено", "state": "idle"})


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    if sid in _active_sessions:
        _active_sessions[sid]["stop_event"].set()
        _active_sessions.pop(sid, None)
    logger.info("Client disconnected: %s", sid)


@socketio.on("connect_device")
def on_connect_device(data: dict):
    ip  = (data.get("ip")  or "").strip()
    key = (data.get("key") or "").strip()
    sid = request.sid

    if not ip or not key:
        emit("status", {"message": "Ошибка: укажите IP и API Key", "state": "error"})
        return

    if sid in _active_sessions:
        _active_sessions[sid]["stop_event"].set()

    t = threading.Thread(target=_esphome_thread, args=(sid, ip, key), daemon=True)
    t.start()


@socketio.on("disconnect_device")
def on_disconnect_device():
    sid = request.sid
    if sid in _active_sessions:
        _active_sessions[sid]["stop_event"].set()
    emit("status", {"message": "Отключено", "state": "disconnected"})


@socketio.on("send_autotune")
def on_send_autotune(data: dict = None):
    sid     = request.sid
    session = _active_sessions.get(sid)

    if not session:
        emit("log", {"message": "Устройство не подключено", "level": "error"})
        return

    loop:   asyncio.AbstractEventLoop = session.get("loop")
    client: APIClient | None          = session.get("client")

    # Ключ берём из события (выбрал пользователь) или из первой найденной кнопки
    key = None
    if data and data.get("key") is not None:
        try:
            key = int(data["key"])
        except (ValueError, TypeError):
            pass
    if key is None:
        key = session.get("autotune_key")

    if loop and client and key is not None:
        future = asyncio.run_coroutine_threadsafe(
            _press_autotune(client, key), loop
        )
        try:
            future.result(timeout=5)
            socketio.emit("log", {"message": "→ Команда Autotune отправлена", "level": "info"}, room=sid)
        except Exception as exc:
            socketio.emit("log", {"message": f"Ошибка отправки команды: {exc}", "level": "error"}, room=sid)
    elif key is None:
        emit("log", {"message": "Кнопка не выбрана или не найдена на устройстве", "level": "error"})
    else:
        emit("log", {"message": "Клиент не готов — попробуйте позже", "level": "error"})


def _esphome_thread(sid: str, ip: str, key: str) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = threading.Event()

    _active_sessions[sid] = {
        "stop_event": stop_event,
        "loop": loop,
        "client": None,
        "autotune_key": None,
    }

    try:
        loop.run_until_complete(_esphome_task(sid, ip, key, stop_event))
    except Exception as exc:
        logger.error("ESPHome thread error [%s]: %s", sid, exc)
    finally:
        loop.close()
        _active_sessions.pop(sid, None)


async def _esphome_task(
    sid: str, ip: str, key: str, stop_event: threading.Event
) -> None:
    global shared_logs

    from .db import device_by_ip, result_save
    saved_dev = device_by_ip(ip)
    device_id = saved_dev["id"] if saved_dev else None

    client = APIClient(address=ip, port=6053, password=None, noise_psk=key)
    if sid in _active_sessions:
        _active_sessions[sid]["client"] = client

    current_block: dict | None = None
    _ansi_re = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def on_log(msg) -> None:
        nonlocal current_block
        try:
            raw_text   = msg.message.decode("utf-8", errors="ignore")
            clean_text = _ansi_re.sub("", raw_text)

            m = re.search(r"\[([A-Z])\]\[([^\]]+)\]:?\s*(.*)", clean_text)
            if not m:
                return

            tag_lower    = m.group(2).lower()
            message_text = m.group(3)
            msg_lower    = message_text.lower()

            if "pid.autotune" not in tag_lower and "pid.autotune" not in msg_lower:
                return

            is_event_start = "pid autotune:" in msg_lower
            is_completed   = "autotune completed" in msg_lower

            if is_event_start:
                if current_block is not None:
                    shared_logs.append(current_block)
                current_block = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "event": message_text,
                }
            else:
                if current_block is not None:
                    current_block["event"] += "\n" + message_text
                else:
                    current_block = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "event": message_text,
                    }

            socketio.emit("log", {"message": message_text, "level": "data"}, room=sid)

            if is_completed and current_block is not None:
                try:
                    rid = result_save(
                        device_ip=ip,
                        started_at=current_block["time"],
                        raw_text=current_block["event"],
                        device_id=device_id,
                    )
                    socketio.emit("result_saved", {"id": rid}, room=sid)
                    logger.info("Autotune result saved: id=%d ip=%s", rid, ip)
                except Exception as exc:
                    logger.error("Failed to save autotune result: %s", exc)
                shared_logs.append(current_block)
                current_block = None

        except Exception as exc:
            logger.error("Log parse error: %s", exc)

    try:
        await client.connect(login=True)

        try:
            entities, _ = await client.list_entities_services()
            buttons = [
                {"key": ent.key, "name": ent.name or ent.object_id}
                for ent in entities
                if isinstance(ent, ButtonInfo)
            ]
            if buttons and sid in _active_sessions:
                _active_sessions[sid]["autotune_key"] = buttons[0]["key"]
            socketio.emit("buttons_ready", {"buttons": buttons}, room=sid)
            logger.info("Buttons on device: %s", buttons)
        except Exception as exc:
            logger.warning("Could not list entities: %s", exc)

        socketio.emit(
            "status",
            {"message": f"Подключено к {ip}", "state": "connected"},
            room=sid,
        )

        client.subscribe_logs(on_log, log_level=5)

        while not stop_event.is_set():
            await asyncio.sleep(1)

    except Exception as exc:
        socketio.emit(
            "status",
            {"message": f"Ошибка: {exc}", "state": "error"},
            room=sid,
        )
        logger.error("ESPHome connection error [%s]: %s", sid, exc)

    finally:
        if current_block is not None:
            shared_logs.append(current_block)
        try:
            await client.disconnect()
        except Exception:
            pass
        socketio.emit(
            "status",
            {"message": "Отключено от устройства", "state": "disconnected"},
            room=sid,
        )


async def _press_autotune(client: APIClient, key: int) -> None:
    client.button_command(key=key)
