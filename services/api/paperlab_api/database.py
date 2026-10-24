import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.environ.get("PAPERLAB_DATABASE_URL", "sqlite:///./.data/paperlab.db")


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    kwargs = {}
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(url, **kwargs)
    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")

    return engine
