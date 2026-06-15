"""Application configuration.

Values are read from environment variables with sensible defaults so the app
runs on macOS today and moves to Ubuntu later by changing only env vars
(primarily ``SERIAL_PORT``). See README for the Ubuntu migration steps.
"""

import os
import secrets


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # Serial port the Arduino is attached to.
    #   macOS:  /dev/cu.usbmodem21201
    #   Ubuntu: /dev/ttyACM0 (or /dev/ttyUSB0); user must be in the `dialout` group
    SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/cu.usbmodem21201")

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
