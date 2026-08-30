import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from greek_law.config import Settings


def test_unknown_key_in_env_file_is_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=local\nTYPO_VAR=oops\n")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=env_file)

    assert "typo_var" in str(exc_info.value)


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(_env_file=None)

    assert settings.log_level == "ERROR"


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "BANANA")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "log_level" in str(exc_info.value)


def test_missing_required_setting_fails_loudly(monkeypatch):
    monkeypatch.delenv("PROBE_REQUIRED", raising=False)

    class ProbeSettings(BaseSettings):
        probe_required: str

    with pytest.raises(ValidationError) as exc_info:
        ProbeSettings(_env_file=None)

    assert "probe_required" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_ollama_model_can_be_overridden_by_env_var(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:30b")

    settings = Settings(_env_file=None)

    assert settings.ollama_model == "qwen3:30b"
