import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_database_url(url: str) -> str:
    """Normalize hosted Postgres URLs for SQLAlchemy + psycopg 3.

    Render/local SQLite continues to work unchanged. Supabase/other PostgreSQL
    connection strings can be pasted as postgres:// or postgresql://.
    """
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./aquametric.db"))
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs = {"future": True, "pool_pre_ping": True}
if not is_sqlite:
    engine_kwargs["pool_recycle"] = 300
engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
