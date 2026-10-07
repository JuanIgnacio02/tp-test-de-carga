"""Tests de la lectura de configuración desde variables de entorno."""

import pytest

from pdf_extractor.config import ConfigError, Settings


def test_defaults_are_used_when_the_environment_is_empty():
    assert Settings.from_env({}) == Settings()


def test_values_are_read_from_the_environment():
    settings = Settings.from_env(
        {
            "PORT": "9000",
            "EXTRACTION_WORKERS": "2",
            "MAX_QUEUE_SIZE": "0",
            "QUEUE_TIMEOUT_SECONDS": "2.5",
            "MAX_UPLOAD_MB": "10",
            "UPLOAD_TIMEOUT_SECONDS": "5",
            "LOG_LEVEL": "debug",
        }
    )

    assert (settings.port, settings.extraction_workers, settings.max_queue_size) == (9000, 2, 0)
    assert (settings.queue_timeout_seconds, settings.max_upload_bytes, settings.log_level) == (2.5, 10_485_760, "DEBUG")
    assert settings.upload_timeout_seconds == 5.0


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("PORT", "abc"),
        ("PORT", "70000"),
        ("EXTRACTION_WORKERS", "0"),
        ("MAX_QUEUE_SIZE", "-1"),
        ("QUEUE_TIMEOUT_SECONDS", "0"),
        ("QUEUE_TIMEOUT_SECONDS", "mucho"),
        ("QUEUE_TIMEOUT_SECONDS", "nan"),
        ("UPLOAD_TIMEOUT_SECONDS", "-1"),
        ("LOG_LEVEL", "VERBOSE"),
    ],
)
def test_invalid_values_are_rejected_with_the_variable_name(variable, value):
    with pytest.raises(ConfigError, match=variable):
        Settings.from_env({variable: value})
