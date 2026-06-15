"""Database models and initialization.

Defines the SQLAlchemy ``db`` instance, the :class:`User` model used for
authentication/authorization, and helpers to create the schema and seed the
initial admin account on first run.
"""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Roles understood by the app.
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLES = (ROLE_ADMIN, ROLE_OPERATOR)

# Seeded on first run only when the users table is empty. This matches the
# credentials documented in the README; change it after the first login.
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "adminPdu2026"


class User(UserMixin, db.Model):
    """An application user.

    ``role`` is either ``"admin"`` (control PDU + manage users) or
    ``"operator"`` (control PDU and view status only).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OPERATOR)

    def set_password(self, password: str) -> None:
        """Hash and store ``password`` (plaintext is never persisted)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if ``password`` matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def to_dict(self) -> dict:
        """Serialize for the user-management API (never exposes the hash)."""
        return {"id": self.id, "username": self.username, "role": self.role}

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"


def init_db(app) -> None:
    """Create tables and seed the admin user if the database is empty.

    Idempotent: safe to call on every startup. The admin account is only
    created when no users exist, so a changed/deleted admin is not recreated.
    """
    with app.app_context():
        db.create_all()
        if User.query.first() is None:
            admin = User(username=DEFAULT_ADMIN_USERNAME, role=ROLE_ADMIN)
            admin.set_password(DEFAULT_ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
