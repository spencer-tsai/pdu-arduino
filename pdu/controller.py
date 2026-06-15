"""PDU controller wrapping a pyfirmata2 Arduino board.

The :class:`PduController` opens the serial connection to an Arduino running
StandardFirmata once, claims a single digital pin as an output, and exposes a
small, thread-safe API to turn the attached PDU relay on/off, toggle it, and
read back the last commanded state.

Design goals:
- The board is opened lazily and at most once. If the Arduino is not connected
  (e.g. during local UI development) the controller degrades gracefully:
  control calls raise :class:`PduError` with a clear message and ``get_state``
  reports ``"unknown"``, so the WebUI still loads.
- Relay polarity is configurable via ``active_high`` so the same code drives
  active-high and active-low relay boards.
"""

import errno
import platform
import threading
from enum import Enum

import serial
from pyfirmata2 import Arduino


def _looks_like_permission_error(exc: Exception) -> bool:
    """True if ``exc`` indicates the OS denied access to the serial device."""
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM):
        return True
    return "permission denied" in str(exc).lower()


def _permission_hint(serial_port: str) -> str:
    """Return an OS-appropriate remediation hint for a serial permission error."""
    if platform.system() == "Linux":
        return (
            f" Permission denied opening {serial_port}. On Linux the device is "
            "owned by the 'dialout' group; add your user with "
            "'sudo usermod -aG dialout \"$USER\"', then log out and back in "
            "(or run 'newgrp dialout') and restart the app."
        )
    return (
        f" Permission denied opening {serial_port}. Ensure no other program is "
        "using the port and that your user may access the serial device."
    )


class _NoResetSerial(serial.Serial):
    """A ``serial.Serial`` that opens without pulsing DTR/RTS.

    Opening/closing the port the normal way asserts/drops DTR, which on an
    Arduino Uno is capacitor-coupled to RESET. That auto-reset reboots the board
    and momentarily floats the output pins (so the relay can glitch). Holding
    DTR/RTS de-asserted across ``open()`` suppresses the reset on the close
    path. The open path still resets at the ``os.open()`` syscall (an OS-level
    behavior that cannot be reliably suppressed in software on macOS/Linux),
    which is why the relay is wired to a plain GPIO (pin 8) rather than pin 13:
    pin 13 is the bootloader's blink LED and would flicker the relay on reset.
    """

    def __init__(self, port=None, *args, **kwargs):
        # Build the port object without opening it (port=None) so the control
        # lines can be set first, then open with the reset suppressed.
        super().__init__(None, *args, **kwargs)
        self.dtr = False
        self.rts = False
        if port is not None:
            self.port = port
            self.open()


class PduState(str, Enum):
    """Last known state of the PDU relay."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class PduError(RuntimeError):
    """Raised when a PDU control action cannot be completed."""


class PduController:
    """Singleton-style wrapper around a pyfirmata2 ``Arduino`` board.

    A single instance should be created at app startup and shared across
    requests. All public methods are guarded by an internal lock so concurrent
    requests cannot interleave serial writes.
    """

    def __init__(self, serial_port: str, pin: int = 8, active_high: bool = True):
        self._serial_port = serial_port
        self._pin_number = pin
        self._active_high = active_high

        self._lock = threading.Lock()
        self._board: Arduino | None = None
        self._pin = None
        # ``None`` until the first successful command; we cannot read the
        # physical line state reliably, so we track what we last commanded.
        self._state: PduState = PduState.UNKNOWN
        self._connect_error: str | None = None

    @property
    def connected(self) -> bool:
        """True if the serial connection to the board is currently open."""
        return self._board is not None

    @property
    def connection_error(self) -> str | None:
        """Human-readable reason the last connection attempt failed, if any."""
        return self._connect_error

    def connect(self) -> None:
        """Open the board and claim the output pin.

        Safe to call repeatedly; a no-op once connected. Raises
        :class:`PduError` (and records :attr:`connection_error`) if the board
        cannot be opened, leaving the controller in a usable "unknown" state.
        """
        with self._lock:
            self._connect_locked()

    def _open_board(self) -> Arduino:
        """Open the Arduino without auto-resetting it.

        pyfirmata2 opens the serial port internally via ``serial.Serial(...)``,
        and a normal open asserts DTR -> the Uno resets -> the bootloader blinks
        pin 13 (our relay) several times. We temporarily swap in
        :class:`_NoResetSerial` (which holds DTR/RTS low across ``open()``) so
        the board is not reset, then restore the original class.
        """
        original_serial = serial.Serial
        serial.Serial = _NoResetSerial
        try:
            return Arduino(self._serial_port)
        finally:
            serial.Serial = original_serial

    def _connect_locked(self) -> None:
        if self._board is not None:
            return
        try:
            board = self._open_board()
            # The iterator thread is required so incoming serial messages are
            # consumed; without it the serial buffer can overflow over time.
            board.samplingOn()
            pin = board.get_pin(f"d:{self._pin_number}:o")
            self._board = board
            self._pin = pin
            self._connect_error = None
        except Exception as exc:  # broad: pyfirmata/serial raise varied errors
            self._board = None
            self._pin = None
            self._state = PduState.UNKNOWN
            message = f"Could not open Arduino on {self._serial_port!r}: {exc}"
            if _looks_like_permission_error(exc):
                message += _permission_hint(self._serial_port)
            self._connect_error = message
            raise PduError(message) from exc

    def _ensure_connected_locked(self):
        if self._board is None:
            self._connect_locked()
        return self._pin

    def _write_locked(self, on: bool) -> PduState:
        pin = self._ensure_connected_locked()
        # active-high: ON -> 1, OFF -> 0; active-low inverts.
        level = 1 if on == self._active_high else 0
        try:
            pin.write(level)
        except Exception as exc:
            self._connect_error = str(exc)
            raise PduError(f"Failed to write pin {self._pin_number}: {exc}") from exc
        self._state = PduState.ON if on else PduState.OFF
        return self._state

    def turn_on(self) -> PduState:
        """Energize the relay (PDU ON). Returns the new state."""
        with self._lock:
            return self._write_locked(True)

    def turn_off(self) -> PduState:
        """De-energize the relay (PDU OFF). Returns the new state."""
        with self._lock:
            return self._write_locked(False)

    def toggle(self) -> PduState:
        """Flip the relay. An unknown state is treated as OFF -> turns ON."""
        with self._lock:
            target_on = self._state != PduState.ON
            return self._write_locked(target_on)

    def get_state(self) -> PduState:
        """Return the last commanded state without touching hardware."""
        with self._lock:
            return self._state

    def close(self) -> None:
        """Close the serial connection and release the board, if open."""
        with self._lock:
            if self._board is not None:
                try:
                    self._board.exit()
                except Exception:
                    pass
            self._board = None
            self._pin = None
            self._state = PduState.UNKNOWN
