from db import SessionLocal
from models import OfficialDataSource
from services import official_data
from services.official_fixture_evidence import _stable_team_key


def test_discovered_team_key_is_stable_across_database_ids():
    first = OfficialDataSource(
        id=1,
        name="RFEN source A",
        provider="RFEN",
        region="Spain",
        url="https://example.test/a",
    )
    rebuilt = OfficialDataSource(
        id=999,
        name="RFEN source B",
        provider="RFEN",
        region="Spain",
        url="https://example.test/b",
    )

    key_a = _stable_team_key(first, "CN Example")
    key_b = _stable_team_key(rebuilt, "CN Example")

    assert key_a == key_b
    assert key_a.startswith("auto-rfen-")
    assert _stable_team_key(first, "Another Club") != key_a


def test_refresh_pass_always_promotes_structured_fixture_evidence(monkeypatch):
    calls = []
    monkeypatch.setattr(official_data, "promote_official_fixtures", lambda db: calls.append(db))

    db = SessionLocal()
    try:
        # Avoid network refreshes: this regression only verifies the automatic
        # promotion hook that runs after every refresh pass.
        runs = official_data.refresh_due_sources(db, force=False, max_sources=0)
        assert runs == []
        assert calls == [db]
    finally:
        db.close()
