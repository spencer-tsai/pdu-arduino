"""Authentication blueprint and Flask-Login wiring.

Provides session-cookie based login/logout backed by the :class:`User` model.
Passwords are verified against the Werkzeug hash stored on the user (see
``models.User.check_password``); plaintext passwords are never stored or logged.

Exports:
- ``login_manager`` - the Flask-Login ``LoginManager`` (initialized in app.py).
- ``auth_bp`` - blueprint with ``/login`` (GET/POST) and ``/logout`` (POST).
- ``admin_required`` - decorator restricting a view to admin users.
"""

from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from models import User

# Initialized against the app in app.py via ``login_manager.init_app(app)``.
login_manager = LoginManager()
# Anonymous users hitting a protected view are redirected here.
login_manager.login_view = "auth.login"
login_manager.login_message_category = "error"

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Reload a user from the session-stored id (Flask-Login callback)."""
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def admin_required(view):
    """Restrict a view to authenticated admin users.

    Stacks on top of authentication: anonymous users are redirected to login
    (via ``@login_required``); authenticated non-admins get a 403.
    """

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _is_safe_redirect_target(target: str | None) -> bool:
    """Allow only same-host relative redirects to avoid open-redirect abuse."""
    if not target:
        return False
    parsed = urlparse(target)
    # Reject absolute URLs and protocol-relative URLs (e.g. //evil.com).
    return not parsed.scheme and not parsed.netloc and target.startswith("/")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Render the login form (GET) and authenticate credentials (POST)."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            # Deliberately vague so we don't reveal which field was wrong.
            flash("Invalid username or password.", "error")
            return render_template("login.html", username=username), 401

        login_user(user, remember=remember)

        next_target = request.args.get("next")
        if _is_safe_redirect_target(next_target):
            return redirect(next_target)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """End the current session and return to the login page."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
