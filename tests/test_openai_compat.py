"""OpenAI-compatible provider against a fake local server (SGLang / vLLM style)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scamantiq.analyzer import Analyzer
from scamantiq.config import PRESETS, Settings, load_settings
from scamantiq.providers import build_provider
from scamantiq.providers.openai_compat import OpenAICompatProvider

MSG = "Pay the $2.99 fee within 12 hours or the parcel will be returned."
ANSWER = {
    "is_suspicious": True,
    "summary": "Deadline pressure.",
    "tactics": [{"label": "urgency", "evidence": ["within 12 hours"], "explanation": "deadline", "confidence": 0.8}],
}


class FakeServer:
    """Minimal /v1/models + /v1/chat/completions server with configurable schema support."""

    def __init__(self, served_model="Qwen/Qwen2.5-7B-Instruct", supports_schema=True, supports_json_object=True):
        self.served_model = served_model
        self.supports_schema = supports_schema
        self.supports_json_object = supports_json_object
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.endswith("/models"):
                    self._send(200, {"object": "list", "data": [{"id": outer.served_model, "object": "model"}]})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n))
                outer.requests.append(payload)
                fmt = payload.get("response_format", {}).get("type")
                if fmt == "json_schema" and not outer.supports_schema:
                    self._send(400, {"error": {"message": "response_format type json_schema is not supported"}})
                    return
                if fmt == "json_object" and not outer.supports_json_object:
                    self._send(400, {"error": {"message": "invalid response_format"}})
                    return
                self._send(200, {"choices": [{"message": {"role": "assistant", "content": json.dumps(ANSWER)}}], "model": payload["model"]})

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}/v1"


def _settings(base_url, model=""):
    return Settings(preset="sglang", provider="openai", base_url=base_url, model=model, api_key="", use_cache=False, timeout=10)


def test_sglang_and_vllm_presets_exist():
    assert PRESETS["sglang"]["provider"] == "openai" and "30000" in PRESETS["sglang"]["base_url"]
    assert PRESETS["vllm"]["provider"] == "openai" and "8000" in PRESETS["vllm"]["base_url"]
    s = load_settings(preset="sglang")
    assert isinstance(build_provider(s), OpenAICompatProvider)
    assert PRESETS["ollama"]["provider"] == "ollama"  # ollama stays available


def test_model_autodetected_and_schema_sent():
    with FakeServer() as srv:
        p = OpenAICompatProvider(_settings(srv.base_url))
        ok, msg = p.healthcheck()
        assert ok and "Qwen/Qwen2.5-7B-Instruct" in msg
        out = p.complete_json("sys", "user", {"type": "object", "properties": {"x": {"type": "string"}}})
        assert json.loads(out)["is_suspicious"] is True
        req = srv.requests[-1]
        assert req["model"] == "Qwen/Qwen2.5-7B-Instruct"
        assert req["response_format"]["type"] == "json_schema"
        assert req["response_format"]["json_schema"]["schema"]["properties"]["x"]["type"] == "string"
        assert req["messages"][0]["role"] == "system"
        assert p.model == "Qwen/Qwen2.5-7B-Instruct"


def test_falls_back_to_json_object_and_remembers():
    with FakeServer(supports_schema=False) as srv:
        p = OpenAICompatProvider(_settings(srv.base_url, model="m"))
        p.complete_json("s", "u", {"type": "object"})
        assert [r["response_format"]["type"] for r in srv.requests] == ["json_schema", "json_object"]
        p.complete_json("s", "u", {"type": "object"})
        assert srv.requests[-1]["response_format"]["type"] == "json_object"
        assert len(srv.requests) == 3  # no renewed json_schema attempt


def test_falls_back_to_no_format():
    with FakeServer(supports_schema=False, supports_json_object=False) as srv:
        p = OpenAICompatProvider(_settings(srv.base_url, model="m"))
        p.complete_json("s", "u", {"type": "object"})
        assert "response_format" not in srv.requests[-1]


def test_healthcheck_reports_wrong_model_and_unreachable():
    with FakeServer() as srv:
        ok, msg = OpenAICompatProvider(_settings(srv.base_url, model="other")).healthcheck()
        assert not ok and "not served" in msg
    ok, msg = OpenAICompatProvider(_settings("http://127.0.0.1:9/v1")).healthcheck()
    assert not ok and "not reachable" in msg


def test_remote_requires_api_key():
    p = OpenAICompatProvider(Settings(preset="groq", provider="openai", base_url="https://api.groq.com/openai/v1", model="m", api_key=""))
    ok, _ = p.healthcheck()
    assert not ok
    with pytest.raises(Exception):
        p.complete_json("s", "u")


def test_analyzer_end_to_end_through_fake_sglang():
    with FakeServer() as srv:
        res = Analyzer(_settings(srv.base_url)).analyze(MSG)
        assert res.error is None and res.labels == ["urgency"]
        assert res.model == "Qwen/Qwen2.5-7B-Instruct" and res.provider == "openai"
