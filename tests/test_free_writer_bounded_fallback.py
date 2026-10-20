"""Provider-free bounded fallback regression tests."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from google.genai.errors import ServerError
from experiments.editorial_engine_v3_phase0 import free_writer_one_shot as writer


def server_503():
    return ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})


def test_first_model_success(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "OUTPUT", tmp_path / "review")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text="# Title\n" + "text " * 150 + writer.SOURCE))))
    result = writer.generate_once(client)
    assert result["model"] == writer.MODELS[0]
    assert result["provider_attempts"] == 1
    assert client.models.generate_content.call_count == 1


def test_fallback_after_503(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "OUTPUT", tmp_path / "review")
    article = "# Title\n" + "text " * 150 + writer.SOURCE
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=[server_503(), SimpleNamespace(text=article)])))
    result = writer.generate_once(client)
    assert result["model"] == writer.MODELS[1]
    assert result["provider_attempts"] == 2
    assert result["attempts"][0]["status"] == "503_unavailable"


def test_all_503_stops_after_three(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "OUTPUT", tmp_path / "review")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=[server_503()] * 3)))
    with pytest.raises(RuntimeError, match="All configured"):
        writer.generate_once(client)
    assert client.models.generate_content.call_count == 3
    assert not writer.OUTPUT.exists()
