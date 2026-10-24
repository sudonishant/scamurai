"""Configuration compatibility: existing PS03 dotenv files must not silently stop working."""
from app.config import Settings


def test_dotenv_supports_legacy_and_canonical_prefixes(tmp_path, monkeypatch):
    for key in ("PS03_DATABASE_URL", "SCAMURAI_DATABASE_URL", "PS03_OSINT_TIMEOUT_SECONDS", "SCAMURAI_OSINT_TIMEOUT_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PS03_DATABASE_URL=sqlite:///./legacy.db\n"
        "SCAMURAI_OSINT_TIMEOUT_SECONDS=7.5\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "sqlite:///./legacy.db"
    assert settings.osint_timeout_seconds == 7.5


def test_canonical_dotenv_value_precedes_legacy_value(tmp_path, monkeypatch):
    for key in ("PS03_DATABASE_URL", "SCAMURAI_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PS03_DATABASE_URL=sqlite:///./legacy.db\n"
        "SCAMURAI_DATABASE_URL=sqlite:///./canonical.db\n",
        encoding="utf-8",
    )
    assert Settings(_env_file=env_file).database_url == "sqlite:///./canonical.db"
