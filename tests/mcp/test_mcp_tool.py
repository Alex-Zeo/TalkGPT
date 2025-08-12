import threading
import time
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

from src.mcp.server import app


def test_transcribe_audio_endpoint_smoke(monkeypatch):
    client = TestClient(app)
    # use a non-existent file to ensure proper error handling
    resp = client.post("/tools/transcribe_audio", json={"input_path": "does_not_exist.wav"})
    assert resp.status_code == 400

