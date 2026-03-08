from flask import Blueprint, abort, jsonify, request

from .db import (
    device_delete,
    device_get,
    device_save,
    devices_list,
    result_delete,
    result_get,
    results_ips,
    results_list,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ───────────────────────────── devices ────────────────────────────────

@api_bp.route("/devices", methods=["GET"])
def get_devices():
    return jsonify(devices_list())


@api_bp.route("/devices/<int:device_id>", methods=["GET"])
def get_device(device_id: int):
    d = device_get(device_id)
    if not d:
        abort(404)
    return jsonify(d)


@api_bp.route("/devices", methods=["POST"])
def create_device():
    data = request.get_json(force=True, silent=True) or {}
    name    = str(data.get("name",    "")).strip()
    ip      = str(data.get("ip",      "")).strip()
    api_key = str(data.get("api_key", "")).strip()

    if not name or not ip or not api_key:
        return jsonify({"error": "Поля name, ip и api_key обязательны"}), 400

    new_id = device_save(name, ip, api_key)
    return jsonify({"id": new_id}), 201


@api_bp.route("/devices/<int:device_id>", methods=["DELETE"])
def remove_device(device_id: int):
    if not device_delete(device_id):
        abort(404)
    return "", 204


# ───────────────────────────── results ────────────────────────────────

@api_bp.route("/results", methods=["GET"])
def get_results():
    device_ip = request.args.get("device_ip") or None
    device_id = request.args.get("device_id", type=int)
    return jsonify(results_list(device_ip=device_ip, device_id=device_id))


@api_bp.route("/results/ips", methods=["GET"])
def get_result_ips():
    return jsonify(results_ips())


@api_bp.route("/results/<int:result_id>", methods=["GET"])
def get_result(result_id: int):
    r = result_get(result_id)
    if not r:
        abort(404)
    return jsonify(r)


@api_bp.route("/results/<int:result_id>", methods=["DELETE"])
def remove_result(result_id: int):
    if not result_delete(result_id):
        abort(404)
    return "", 204
