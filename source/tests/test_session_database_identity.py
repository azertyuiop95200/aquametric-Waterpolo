from sqlalchemy import create_engine
from services.session_database_identity import database_bound_session_secret


def test_session_key_survives_restart_but_rejects_cookies_after_database_loss(tmp_path):
    first = create_engine(f"sqlite:///{tmp_path / 'original.db'}")
    original_key = database_bound_session_secret(first, "deployment-secret")
    first.dispose()
    restarted = create_engine(f"sqlite:///{tmp_path / 'original.db'}")
    assert database_bound_session_secret(restarted, "deployment-secret") == original_key
    replacement = create_engine(f"sqlite:///{tmp_path / 'replacement.db'}")
    assert database_bound_session_secret(replacement, "deployment-secret") != original_key
    assert database_bound_session_secret(restarted, "other-deployment") != original_key
