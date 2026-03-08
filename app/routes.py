import socket
import time

import zeroconf
from flask import Blueprint, jsonify, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/scan_mdns")
def scan_mdns():
    devices: list[dict] = []

    class _Listener:
        def remove_service(self, *args):
            pass

        def update_service(self, *args):
            pass

        def add_service(self, zc, type_, name):
            try:
                info = zc.get_service_info(type_, name)
                if info and info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    name_clean = name.split(".")[0]
                    ip_tuple = tuple(map(int, ip.split(".")))
                    devices.append(
                        {
                            "ip": ip,
                            "text": f"{ip} — {name_clean}",
                            "ip_tuple": ip_tuple,
                        }
                    )
            except Exception:
                pass

    zc = zeroconf.Zeroconf()
    zeroconf.ServiceBrowser(zc, "_esphomelib._tcp.local.", _Listener())
    time.sleep(4)
    zc.close()

    devices.sort(key=lambda d: d["ip_tuple"])
    return jsonify([{"ip": d["ip"], "text": d["text"]} for d in devices])


@main_bp.route("/get_json")
def get_json():
    from .sockets import shared_logs

    return jsonify(shared_logs)
