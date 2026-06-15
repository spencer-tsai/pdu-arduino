"""Application configuration.

Values are read from environment variables with sensible defaults. The serial
port is auto-detected for the current OS (macOS vs Ubuntu/Linux) so the app
runs on either platform with no code changes; ``SERIAL_PORT`` overrides it.
See README for the Ubuntu migration steps.
"""

import glob
import os
import platform
import secrets

from serial.tools import list_ports


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Per-OS USB-serial device naming for an attached Arduino. macOS exposes the
# board's USB CDC driver as /dev/cu.usbmodem* (or /dev/cu.usbserial* for FTDI
# clones); Ubuntu/Linux uses the cdc_acm driver -> /dev/ttyACM* (or the FTDI
# driver -> /dev/ttyUSB*).
_SERIAL_PORT_PROFILES = {
    "Darwin": {
        "prefixes": ("/dev/cu.usbmodem", "/dev/cu.usbserial"),
        "globs": ("/dev/cu.usbmodem*", "/dev/cu.usbserial*"),
        "fallback": "/dev/cu.usbmodem21201",
    },
    "Linux": {
        "prefixes": ("/dev/ttyACM", "/dev/ttyUSB"),
        "globs": ("/dev/ttyACM*", "/dev/ttyUSB*"),
        "fallback": "/dev/ttyACM0",
    },
}


def detect_serial_port() -> str:
    """Auto-select the Arduino serial device for the current OS.

    Resolution order:

    1. The first connected device whose name matches the current OS's
       USB-serial driver naming (via pyserial's port enumeration).
    2. The first device matching the OS glob patterns under ``/dev``.
    3. A typical fallback name for the OS.

    Set the ``SERIAL_PORT`` environment variable to override entirely.
    """
    profile = _SERIAL_PORT_PROFILES.get(platform.system())
    if profile is None:
        # Unknown OS (e.g. Windows): let pyserial pick the first port, if any.
        ports = sorted(p.device for p in list_ports.comports())
        return ports[0] if ports else "/dev/ttyACM0"

    for port in sorted(p.device for p in list_ports.comports()):
        if port.startswith(profile["prefixes"]):
            return port
    for pattern in profile["globs"]:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return profile["fallback"]


class Config:
    # Operating system, used for OS-aware defaults and startup logging.
    PLATFORM = platform.system()

    # Serial port the Arduino is attached to. Auto-detected per-OS:
    #   macOS:  /dev/cu.usbmodem* (or /dev/cu.usbserial*)
    #   Ubuntu: /dev/ttyACM* (or /dev/ttyUSB*); user must be in the `dialout` group
    # Set SERIAL_PORT to override the auto-detection.
    SERIAL_PORT = os.environ.get("SERIAL_PORT") or detect_serial_port()

    # Arduino digital pin driving the PDU relay.
    # NOTE: avoid pin 13 -- it is the Uno's onboard LED and the bootloader
    # blinks it on every reset, so the relay would flicker on connect. Pin 8 is
    # a plain GPIO with no special function.
    PDU_PIN = int(os.environ.get("PDU_PIN", "8"))

    # Relay polarity. True => writing HIGH (1) turns the PDU ON.
    # Set ACTIVE_HIGH=false for active-low relay boards.
    ACTIVE_HIGH = _env_bool("ACTIVE_HIGH", True)

    # Flask session signing key. A random key is generated for dev if unset;
    # set SECRET_KEY in production so sessions survive restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

    # SQLAlchemy database URL. Defaults to a local SQLite file.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///users.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # TLS / HTTPS. When enabled, the dev server is served over HTTPS using the
    # certificate/key below. Generate a self-signed pair with:
    #   openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/key.pem \
    #     -out certs/cert.pem -days 825 -subj "/CN=localhost" \
    #     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    # NOTE: these are namespaced (PDU_ prefix) to avoid colliding with the
    # standard OpenSSL ``SSL_CERT_FILE`` env var, which points to the CA trust
    # bundle and would break TLS verification for outgoing requests if reused.
    USE_HTTPS = _env_bool("USE_HTTPS", True)
    SSL_CERT_FILE = os.environ.get("PDU_SSL_CERT_FILE", "certs/cert.pem")
    SSL_KEY_FILE = os.environ.get("PDU_SSL_KEY_FILE", "certs/key.pem")

    # Port the server listens on (8443 by default for HTTPS).
    PORT = int(os.environ.get("PORT", "8443"))

    # Session cookie hardening. Only send the session cookie over HTTPS when
    # TLS is enabled, never expose it to JavaScript, and use Lax SameSite.
    SESSION_COOKIE_SECURE = USE_HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
