# PDU Web Control

A Python/Flask web app that turns a PDU on/off by driving an Arduino Uno
digital pin (default pin 8) over the Firmata protocol. It includes a multi-user
login system with roles (`admin` / `operator`), a WebUI dashboard, and a REST
API.

Designed to run on macOS now and move to Ubuntu later by changing only the
serial-port configuration.

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

Then open the WebUI in a browser and log in.

### Default admin credentials

On first run an `admin` user is seeded with password `pDU@binDU2026`
(only if no users exist). **Change this password after first login.**

## Configuration

All settings are read from environment variables (see `config.py`):

| Variable      | Default                     | Description                                        |
| ------------- | --------------------------- | -------------------------------------------------- |
| `SERIAL_PORT` | `/dev/cu.usbmodem21201`     | Serial device for the Arduino.                     |
| `PDU_PIN`     | `8`                         | Digital pin driving the relay (avoid 13; see below). |
| `ACTIVE_HIGH` | `true`                      | `true`: HIGH = ON. Set `false` for active-low relays. |
| `SECRET_KEY`  | random (dev)                | Flask session signing key; set in production.      |
| `DATABASE_URL`| `sqlite:///users.db`        | SQLAlchemy database URL.                            |

Example:

```bash
SERIAL_PORT=/dev/cu.usbmodem21201 SECRET_KEY=$(openssl rand -hex 32) uv run python app.py
```

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

## Ubuntu migration (later)

No code changes are required:

1. Set the serial port, e.g. `SERIAL_PORT=/dev/ttyACM0` (or `/dev/ttyUSB0`).
2. Add your user to the `dialout` group so it can access the serial device:

   ```bash
   sudo usermod -aG dialout "$USER"
   ```

   Log out and back in for the group change to take effect.
3. Optionally add a `systemd` service to run the app on boot.
