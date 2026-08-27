from sqlmodel import Session, select

from .model import User, Role
from .schemas import UserCreate
from app.auth.security import hash_password


def get_user_by_email(session: Session, email: str) -> User | None:

    normalized_email = email.strip().lower()
    statement = select(User).where(User.email == normalized_email)
    return session.exec(statement).first()

def create_user(session: Session, user_data: UserCreate) -> User:

    email = user_data.email.strip().lower()

    existing_user = get_user_by_email(session, email)
    if existing_user:
        raise ValueError("Ein Benutzer mit dieser E-Mail existiert bereits.")

    user = User(
        email=email,
        name=user_data.name.strip(),
        password_hash=hash_password(user_data.password)
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def get_user_by_id(session: Session,user_id: int) -> User | None:
    return session.get(User, user_id)


def add_role_to_user(session: Session, user: User, role: Role) -> User:

    if role not in user.roles:
        user.roles.append(role)
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


def remove_role_from_user(session: Session, user: User, role: Role) -> User:

    if role in user.roles:
        user.roles.remove(role)
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


def get_role_by_name(session: Session, name: str) -> Role | None:

    return session.exec(
        select(Role).where(Role.name == name)
    ).first()
