from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = "esphome-pid-logger-secret-key"

    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    from .db import init_db
    init_db()

    from .routes import main_bp
    app.register_blueprint(main_bp)

    from .api import api_bp
    app.register_blueprint(api_bp)

    from . import sockets  # noqa: F401 — registers socket events

    return app
