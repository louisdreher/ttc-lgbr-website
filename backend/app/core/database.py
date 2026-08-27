from unittest import skip

from sqlmodel import Session, SQLModel, create_engine

# import nötig für db erstellung
import backend.app.model_registry
from backend.app.core.settings import settings
from backend.app.domains.users.model import create_default_roles

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
