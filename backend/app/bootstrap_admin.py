import os

from sqlmodel import Session, select

from app.core.security import hash_password
from app.db.models import RoleName, User, UserRole
from app.db.session import engine


def main() -> None:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or len(password) < 12:
        raise SystemExit("Set BOOTSTRAP_ADMIN_EMAIL and a 12+ character BOOTSTRAP_ADMIN_PASSWORD")
    with Session(engine) as session:
        if session.exec(select(User).where(User.email == email)).first():
            raise SystemExit("Admin email already exists; refusing to elevate an existing account")
        user = User(
            email=email, display_name="OMNIVA Administrator", password_hash=hash_password(password)
        )
        session.add(user)
        session.flush()
        session.add(UserRole(user_id=user.id, role=RoleName.admin))
        session.commit()
    print("Bootstrap administrator created")


if __name__ == "__main__":
    main()
