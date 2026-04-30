"""SQLModel engine, session helpers; SQL migrations live under db/migrations/."""

from sqlmodel import Session, SQLModel, create_engine

from app.core.db_runtime import resolve_database_url

DATABASE_URL = resolve_database_url()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
