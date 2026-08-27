from unittest import skip

# import nötig für db erstellung
import app.model_registry
from app.core.settings import settings
from app.domains.users.model import create_default_roles
from sqlmodel import Session, SQLModel, create_engine

engine = create_engine(settings.database_url)


def get_session():
    with Session(engine) as session:
        yield session


def initialize_database():
    # from now one using alembic for databes migration
    a = 2
    # SQLModel.metadata.create_all(engine)
    # with Session(engine) as session:
    #     create_default_roles(session)
