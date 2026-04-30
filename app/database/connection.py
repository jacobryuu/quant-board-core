import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Use an environment variable for production. The fallback is a local SQLite
# database so credentials are not embedded in source code.
DATABASE_URL = os.getenv(
    "MASTER_DATABASE_URL",
    "sqlite:///./quant_board.db",
)


def _create_engine(database_url: str):
    engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_recycle": 3600,
            }
        )
    return create_engine(database_url, **engine_kwargs)


engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_tables():
    Base.metadata.create_all(bind=engine)
