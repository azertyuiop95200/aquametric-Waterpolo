"""Invalidate signed browser sessions if their underlying database is replaced."""
import hashlib
import hmac
import secrets

from sqlalchemy import Column, MetaData, String, Table, select
from sqlalchemy.exc import IntegrityError


def database_bound_session_secret(engine, application_secret: str) -> str:
    # Numeric user IDs can be reused after an ephemeral SQLite reset. A valid
    # cookie from the old database must never authenticate as a new user ID 1.
    metadata = MetaData()
    identity = Table("installation_identity", metadata,
                     Column("key", String(32), primary_key=True),
                     Column("value", String(64), nullable=False))
    metadata.create_all(engine)
    with engine.connect() as connection:
        nonce = connection.scalar(select(identity.c.value).where(identity.c.key == "session_epoch"))
    if nonce is None:
        try:
            with engine.begin() as connection:
                connection.execute(identity.insert().values(key="session_epoch", value=secrets.token_hex(32)))
        except IntegrityError:
            # Another app process initialized the same database first.
            pass
        with engine.connect() as connection:
            nonce = connection.scalar(select(identity.c.value).where(identity.c.key == "session_epoch"))
    return hmac.new(application_secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
