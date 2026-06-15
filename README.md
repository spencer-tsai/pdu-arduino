# PDU Web Control

A Python/Flask web app that turns a PDU on/off by driving an Arduino Uno
digital pin (default pin 8) over the Firmata protocol. It includes a multi-user
login system with roles (`admin` / `operator`), a WebUI dashboard, and a REST
API.

Designed to run on macOS and Ubuntu/Linux: the serial device is auto-detected
per OS, so no code or config changes are needed to move between them.

## Architecture

```
Browser (WebUI) --HTTP/REST + session cookie--> Flask backend
Flask --SQLAlchemy--> SQLite (users.db)
Flask --pyfirmata2 over serial--> Arduino Uno (StandardFirmata)
Arduino --pin 8 HIGH/LOW--> PDU relay
```

## Requirements

- [uv](https://docs.astral.sh/uv/) for environment and dependency management.
- An Arduino Uno running the **StandardFirmata** sketch (flash it via the
  Arduino IDE: *File -> Examples -> Firmata -> StandardFirmata*, then Upload).
- The board connected over USB.

## Setup

Install dependencies into a project-local `.venv` (created and managed by uv):

```bash
uv sync
```

Run the app (uv uses the project `.venv` implicitly, no manual activation):

```bash
uv run python app.py
```

The app serves over **HTTPS** by default on port `8443`. Open the WebUI at
[https://localhost:8443](https://localhost:8443) and log in. Because the bundled
certificate is self-signed, your browser will show a one-time security warning —
accept it to proceed (see [HTTPS / TLS](#https--tls) below).

### Default admin credentials

Current credentials:

- **Username:** `admin`
- **Password:** `adminPdu2026`

On the **very first run** (when the database has no users) an `admin` user is
seeded with these same credentials (defined in `models.py`). The seed is used
only to create the account; once the account exists it is never reset, so a
later password change persists across restarts.

**Keep this password secure** — it is stored hashed in the database. To change
it from the CLI:

```bash
uv run python -c "from app import app; from models import db, User; \
app.app_context().push(); u=User.query.filter_by(username='admin').first(); \
u.set_password('your-new-password'); db.session.commit(); print('updated')"
```

## Configuration

All settings are read from environment variables (see `config.py`):

| Variable      | Default                     | Description                                        |
| ------------- | --------------------------- | -------------------------------------------------- |
| `SERIAL_PORT` | auto-detected (per OS)      | Serial device for the Arduino; overrides OS auto-detection. |
| `PDU_PIN`     | `8`                         | Digital pin driving the relay (avoid 13; see below). |
| `ACTIVE_HIGH` | `true`                      | `true`: HIGH = ON. Set `false` for active-low relays. |
| `SECRET_KEY`  | random (dev)                | Flask session signing key; set in production.      |
| `DATABASE_URL`| `sqlite:///users.db`        | SQLAlchemy database URL.                            |
| `USE_HTTPS`   | `true`                      | Serve over HTTPS (TLS). Set `false` for plain HTTP. |
| `PORT`        | `8443`                      | Port to listen on.                                 |
| `PDU_SSL_CERT_FILE`| `certs/cert.pem`       | TLS certificate (PEM).                             |
| `PDU_SSL_KEY_FILE`| `certs/key.pem`         | TLS private key (PEM).                             |

Example (all env vars are optional; the serial port is auto-detected):

```bash
# Override the auto-detected port and set a stable signing key:
SERIAL_PORT=/dev/ttyACM0 SECRET_KEY=$(openssl rand -hex 32) uv run python app.py
```

## HTTPS / TLS

The app serves over HTTPS by default (`USE_HTTPS=true`) using the cert/key in
`certs/`. A self-signed pair is generated during setup; regenerate it with:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/key.pem -out certs/cert.pem -days 825 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Notes:

- The `certs/` directory is git-ignored — never commit private keys. Each
  deployment generates its own pair.
- Self-signed certs trigger a browser warning; accept it (or import the cert as
  trusted). For a public deployment, use a CA-issued cert (e.g. Let's Encrypt),
  ideally terminated at a reverse proxy such as nginx in front of a production
  WSGI server.
- When `USE_HTTPS=true`, the session cookie is marked `Secure` so it is only
  sent over TLS. To run plain HTTP instead, set `USE_HTTPS=false`.
- If the cert/key files are missing, the server falls back to an ephemeral
  self-signed certificate (requires the `cryptography` package).

## Roles

- **admin**: control the PDU and manage users (create/delete, assign roles).
- **operator**: control the PDU and view status only; cannot manage users.

## Hardware notes

- The relay pin (default **pin 8**) is configured as OUTPUT. With
  `ACTIVE_HIGH=true`, ON writes HIGH (1) and OFF writes LOW (0).
- **Wire the relay's signal input to pin 8, not pin 13.** Pin 13 is the Uno's
  onboard LED, and the bootloader blinks it on every reset. Because opening the
  serial port resets the board (an OS-level DTR pulse on macOS/Linux that
  cannot be reliably suppressed in software), a relay on pin 13 would flicker
  on/off each time the app starts. Pin 8 is a plain GPIO with no such function.
- On reset (which happens once when the app opens the port), all pins briefly
  float as inputs for ~1-2 s while the bootloader runs, so the relay may drop
  momentarily before the app drives the pin. Choose the relay's wiring so this
  fail-safe state is acceptable (e.g. an active-high relay stays OFF while the
  pin floats). The board is held open for the app's lifetime, so this only
  occurs at startup, not on each On/Off command.
- To eliminate even the startup reset entirely, add a ~10 µF capacitor between
  the Uno's `RESET` and `GND` pins (remove it when uploading a new sketch).

## OS detection / serial port

The app detects the operating system at startup and picks the matching
USB-serial device naming automatically (logged on boot as
`Detected OS ... ; using serial port ...`):

| OS             | Driver / device naming                          |
| -------------- | ----------------------------------------------- |
| macOS (Darwin) | `/dev/cu.usbmodem*` (or `/dev/cu.usbserial*`)   |
| Ubuntu (Linux) | `/dev/ttyACM*` (cdc_acm) or `/dev/ttyUSB*` (FTDI) |

It first looks for a connected device matching the OS naming (via pyserial's
port enumeration), then globs `/dev`, then falls back to a typical name for the
OS. Set `SERIAL_PORT` to override the auto-detection.

## Ubuntu migration (later)

No code changes are required — the serial device is auto-detected on Linux:

1. (Optional) Pin a specific device with `SERIAL_PORT=/dev/ttyACM0` if multiple
   USB-serial devices are attached; otherwise auto-detection handles it.
2. Add your user to the `dialout` group so it can access the serial device:

   ```bash
   sudo usermod -aG dialout "$USER"
   ```

   Log out and back in for the group change to take effect.
3. Optionally add a `systemd` service to run the app on boot.
