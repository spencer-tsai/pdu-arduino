# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Flask web app that switches a PDU relay on/off by driving an Arduino Uno digital pin (default pin 8) over Firmata (`pyfirmata2`). The Arduino must run the stock **StandardFirmata** sketch — there is no Arduino source in this repo. Multi-user login (roles `admin` / `operator`), WebUI dashboard, and a JSON REST API. Runs on macOS and Linux with per-OS serial auto-detection.

## Commands

Dependencies are managed with **uv** (Python ≥ 3.11, project-local `.venv`):

```bash
uv sync                          # install deps
uv run python app.py             # run (HTTPS on :8443, debug on, reloader off)
USE_HTTPS=false uv run python app.py   # plain HTTP
```

- There is no test suite, linter, or formatter configured.
- Do **not** use `uv run flask --app app run` with default settings: the Flask CLI ignores the `ssl_context`/`PORT` wiring in `app.py` and serves HTTP, while `SESSION_COOKIE_SECURE` is still true, so logins silently fail. If needed, use `USE_HTTPS=false uv run flask --app app run`.
- TLS cert/key live in `certs/` (git-ignored); if missing, the app falls back to an ephemeral "adhoc" cert. See README for the `openssl` command to regenerate.
- SQLite DB is at `instance/users.db` (Flask instance folder). Default admin is seeded only when the DB has no users (`models.init_db`); credentials are in `models.py` / README.
- All configuration comes from env vars in `config.py` (`SERIAL_PORT`, `PDU_PIN`, `ACTIVE_HIGH`, `SECRET_KEY`, `DATABASE_URL`, `USE_HTTPS`, `PORT`, `PDU_SSL_CERT_FILE`, `PDU_SSL_KEY_FILE`). The TLS vars are `PDU_`-prefixed on purpose to avoid clashing with OpenSSL's `SSL_CERT_FILE`.

## Architecture

- `app.py` — `create_app()` factory: loads `Config`, inits SQLAlchemy + Flask-Login, seeds DB, registers `auth_bp` and `api_bp`, and creates **one shared `PduController`** stored in `app.extensions["pdu_controller"]` (closed via `atexit`). Also serves the HTML pages (`/` dashboard, `/users` admin-only). A module-level `app = create_app()` exists, so importing `app` opens the serial port.
- `pdu/controller.py` — `PduController`: thread-safe (single `threading.Lock`) wrapper around a pyfirmata2 `Arduino`. Connects lazily/at most once; if the board is absent, startup still succeeds, `get_state()` returns `unknown`, and control calls raise `PduError` (API maps this to HTTP 503). State is the **last commanded** value, not read back from hardware. `ACTIVE_HIGH` inverts the written level.
  - `_NoResetSerial` + `_open_board()` monkey-patch `serial.Serial` during `Arduino(...)` construction to hold DTR/RTS low and avoid resetting the Uno on close. The OS still resets the board on `open()`; this is a hardware limitation (documented in README — fix is a 10 µF cap on RESET–GND). Don't move the relay to pin 13 (bootloader LED blinks on reset).
- `config.py` — `detect_serial_port()` picks the device per `platform.system()` (Darwin: `/dev/cu.usbmodem*|usbserial*`; Linux: `/dev/ttyACM*|ttyUSB*`), via pyserial enumeration → `/dev` glob → fallback name. Evaluated at import time of `Config`.
- `auth.py` — session-cookie login/logout, `login_manager`, `admin_required` decorator (login required + 403 for non-admins), safe `next` redirect check.
- `api.py` — `/api` blueprint: `GET /pdu/status`, `POST /pdu/on|off|toggle` (any logged-in user); `GET/POST /users`, `DELETE /users/<id>` (admin; prevents deleting self or the last admin). Gets the controller via `current_app.extensions`, never imports app wiring.
- `models.py` — `User` (Werkzeug password hash, `role`), `ROLES` constants, `init_db`.
- Frontend: Jinja templates extend `templates/base.html`; vanilla JS in `static/js/` (`app.js` polls `/api/pdu/status` on an interval; `users.js` drives the admin page). Theme (light default / dark) is `html[data-theme="dark"]` persisted in `localStorage["pdu-theme"]`: an inline pre-paint script in `base.html` applies it before first paint, and `theme.js` wires the `.theme-seg` toggle buttons. Colors are CSS variables in `static/css/style.css` (`:root` = light).
