"""Configuration uses the repository's canonical SCAMURAI_ prefix."""
from app.config import Settings


def test_canonical_dotenv_values_are_loaded(tmp_path, monkeypatch):
    for key in ("SCAMURAI_DATABASE_URL", "SCAMURAI_OSINT_TIMEOUT_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SCAMURAI_DATABASE_URL=sqlite:///./canonical.db\n"
        "SCAMURAI_OSINT_TIMEOUT_SECONDS=7.5\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "sqlite:///./canonical.db"
    assert settings.osint_timeout_seconds == 7.5


def test_legacy_prefixed_dotenv_values_are_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("SCAMURAI_DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("LEGACY_DATABASE_URL=sqlite:///./legacy.db\n", encoding="utf-8")
    assert Settings(_env_file=env_file).database_url == "sqlite:///./scamurai_dev.db"


def test_development_authentication_is_off_by_default(monkeypatch):
    monkeypatch.delenv("SCAMURAI_DEV_AUTH_ENABLED", raising=False)
    assert Settings(_env_file=None).dev_auth_enabled is False
