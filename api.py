"""REST API blueprint.

Exposes JSON endpoints for controlling the PDU and (for admins) managing
users. Every endpoint requires an authenticated session; the user-management
endpoints additionally require the ``admin`` role via :func:`admin_required`.

The PDU controller is not imported directly to keep this blueprint decoupled
from app wiring. ``app.py`` must register the shared
:class:`pdu.controller.PduController` instance as
``app.extensions["pdu_controller"]`` before the first request.
"""

from flask import Blueprint, abort, current_app, jsonify, request
from flask_login import current_user, login_required

from auth import admin_required
from models import ROLE_ADMIN, ROLES, User, db
from pdu.controller import PduController, PduError

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _controller() -> PduController:
    """Return the shared PDU controller registered by ``app.py``."""
    controller = current_app.extensions.get("pdu_controller")
    if controller is None:  # pragma: no cover - misconfiguration guard
        raise RuntimeError(
            "PDU controller is not registered; app.py must set "
            "app.extensions['pdu_controller']."
        )
    return controller


def _status_payload(controller: PduController) -> dict:
    """Build the JSON body describing the current PDU state."""
    return {
        "state": controller.get_state().value,
        "connected": controller.connected,
        "error": controller.connection_error,
    }


# --- PDU control (any authenticated user) --------------------------------


@api_bp.get("/pdu/status")
@login_required
def pdu_status():
    """Report the last commanded PDU state without touching hardware."""
    return jsonify(_status_payload(_controller()))


@api_bp.post("/pdu/on")
@login_required
def pdu_on():
    """Turn the PDU on."""
    controller = _controller()
    try:
        controller.turn_on()
    except PduError as exc:
        return jsonify({**_status_payload(controller), "error": str(exc)}), 503
    return jsonify(_status_payload(controller))


@api_bp.post("/pdu/off")
@login_required
def pdu_off():
    """Turn the PDU off."""
    controller = _controller()
    try:
        controller.turn_off()
    except PduError as exc:
        return jsonify({**_status_payload(controller), "error": str(exc)}), 503
    return jsonify(_status_payload(controller))


@api_bp.post("/pdu/toggle")
@login_required
def pdu_toggle():
    """Flip the PDU state."""
    controller = _controller()
    try:
        controller.toggle()
    except PduError as exc:
        return jsonify({**_status_payload(controller), "error": str(exc)}), 503
    return jsonify(_status_payload(controller))


# --- User management (admin only) ----------------------------------------


@api_bp.get("/users")
@admin_required
def list_users():
    """List all users (never exposes password hashes)."""
    users = User.query.order_by(User.username).all()
    return jsonify([user.to_dict() for user in users])


@api_bp.post("/users")
@admin_required
def create_user():
    """Create a user from JSON ``{username, password, role}``."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if role not in ROLES:
        return jsonify({"error": f"role must be one of {list(ROLES)}"}), 400
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "username already exists"}), 409

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@api_bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    """Delete a user by id.

    Guards against locking the app out: admins cannot delete their own
    account, and the final remaining admin cannot be removed.
    """
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        return jsonify({"error": "you cannot delete your own account"}), 400
    if user.is_admin and User.query.filter_by(role=ROLE_ADMIN).count() <= 1:
        return jsonify({"error": "cannot delete the last admin"}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({"deleted": user_id})
