"""Application entry point and Flask app factory.

Wires together the configuration, database, authentication, REST API, and the
shared PDU controller, and serves the WebUI templates (login, dashboard, and
the admin-only user management page).

Run locally with uv::

    uv run python app.py

This entry point honors the TLS settings in ``config.py`` (HTTPS on ``PORT``,
default 8443). The Flask CLI (``uv run flask --app app run``) does NOT apply the
``ssl_context``/``PORT`` wiring below, so it serves plain HTTP; because the
session cookie is marked ``Secure`` whenever ``USE_HTTPS`` is true (the
default), logins would silently fail over that HTTP path. If you must use the
Flask CLI, disable TLS so the cookie is not ``Secure``-only::

    USE_HTTPS=false uv run flask --app app run
"""

import atexit
import os

from flask import Flask, redirect, render_template, url_for
from flask_login import login_required

from api import api_bp
from auth import admin_required, auth_bp, login_manager
from config import Config
from models import db, init_db
from pdu.controller import PduController


def _create_controller(app: Flask) -> PduController:
    """Build the shared PDU controller and attempt an initial connection.

    Connection failures are intentionally swallowed here so the WebUI still
    loads when the Arduino is absent (e.g. during local UI development). The
    controller records the error and reports an ``unknown`` state until a board
    becomes available; control endpoints surface the error to the client.
    """
    controller = PduController(
        serial_port=app.config["SERIAL_PORT"],
        pin=app.config["PDU_PIN"],
        active_high=app.config["ACTIVE_HIGH"],
    )
    try:
        controller.connect()
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash boot
        app.logger.warning("PDU controller could not connect at startup: %s", exc)
    return controller


def create_app(config_class: type[Config] = Config) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.logger.info(
        "Detected OS %s; using serial port %s",
        app.config["PLATFORM"],
        app.config["SERIAL_PORT"],
    )

    # Core extensions.
    db.init_app(app)
    login_manager.init_app(app)

    # Create tables and seed the admin user on first run.
    init_db(app)

    # Blueprints: authentication and the REST API.
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    # Shared PDU controller, accessible to the API via app.extensions.
    controller = _create_controller(app)
    app.extensions["pdu_controller"] = controller
    atexit.register(controller.close)

    # --- WebUI pages -----------------------------------------------------

    @app.route("/")
    @login_required
    def dashboard():
        """Main control page: big On/Off toggle plus live status."""
        return render_template("dashboard.html")

    @app.route("/users")
    @admin_required
    def users():
        """Admin-only user management page."""
        return render_template("users.html")

    @app.route("/favicon.ico")
    def favicon():
        """Avoid noisy 404s from browsers requesting a favicon."""
        return "", 204

    return app


app = create_app()


def _resolve_ssl_context(flask_app: Flask):
    """Build the ``ssl_context`` for ``app.run`` based on configuration.

    Returns ``None`` (plain HTTP) when HTTPS is disabled. Otherwise prefers the
    configured cert/key pair; if those files are missing it falls back to an
    ephemeral self-signed cert ("adhoc"), raising a clear error if the
    ``cryptography`` package needed for that fallback is not installed.
    """
    if not flask_app.config["USE_HTTPS"]:
        return None

    cert = flask_app.config["SSL_CERT_FILE"]
    key = flask_app.config["SSL_KEY_FILE"]
    if os.path.exists(cert) and os.path.exists(key):
        return (cert, key)

    flask_app.logger.warning(
        "TLS cert/key not found at %r / %r; using an ephemeral self-signed "
        "certificate. Generate a persistent pair (see config.py) to avoid this.",
        cert,
        key,
    )
    return "adhoc"


if __name__ == "__main__":
    ssl_context = _resolve_ssl_context(app)
    scheme = "https" if ssl_context else "http"
    port = app.config["PORT"]
    app.logger.info("Serving on %s://0.0.0.0:%s", scheme, port)
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        use_reloader=False,
        ssl_context=ssl_context,
    )
