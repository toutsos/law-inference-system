import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from greek_law.config import Settings


def test_unknown_key_in_env_file_is_rejected(tmp_path):
    """A key in .env that Settings does not declare is an error.

    This is `extra="forbid"` doing its job. Without it, `OLAMA_MODEL=...` (one
    L) would be accepted in silence and the default used instead — you would be
    running a different model than the file says, with nothing to indicate it.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=local\nTYPO_VAR=oops\n")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=env_file)

    assert "typo_var" in str(exc_info.value)


def test_env_var_overrides_default(monkeypatch):
    """An environment variable beats the field default.

    Pins the precedence the whole config seam depends on. Catches the wiring
    breaking — an `env_prefix` added to `model_config`, or a field renamed —
    after which the process would keep running on defaults and ignore the
    environment entirely, without raising.
    """
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(_env_file=None)

    assert settings.log_level == "ERROR"


def test_invalid_log_level_is_rejected(monkeypatch):
    """An unknown log level fails at startup, not at first use.

    This is the `Literal[...]` type earning its place. Widen it to `str` and a
    typo like "DEBGU" is accepted here and blows up later, inside the logging
    call, in whatever code path happened to log first.
    """
    monkeypatch.setenv("LOG_LEVEL", "BANANA")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "log_level" in str(exc_info.value)


def test_missing_required_setting_fails_loudly(monkeypatch):
    """A field with no default and no value stops the process immediately.

    Deliberately probes a throwaway `ProbeSettings`, not `Settings`, because
    every real field currently has a default. It pins the behaviour we are
    relying on for the first secret-bearing setting (a hosted provider's API
    key): fail at startup, never `None` propagating into an HTTP header.
    """
    monkeypatch.delenv("PROBE_REQUIRED", raising=False)

    class ProbeSettings(BaseSettings):
        probe_required: str

    with pytest.raises(ValidationError) as exc_info:
        ProbeSettings(_env_file=None)

    assert "probe_required" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_ollama_model_can_be_overridden_by_env_var(monkeypatch):
    """OLLAMA_MODEL in the environment actually reaches Settings.ollama_model.

    This is the knob the deferred Krikri-vs-Qwen comparison flips. If the
    override silently no-ops, the comparison runs the same model twice and
    produces a wrong *finding* about Greek specialisation — far more expensive
    than a crash, because nothing looks broken.
    """
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:30b")

    settings = Settings(_env_file=None)

    assert settings.ollama_model == "qwen3:30b"
