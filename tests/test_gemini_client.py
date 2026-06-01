import json
from unittest.mock import patch

from backend.ai_service.services.gemini_client import GeminiClient


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "SELECT 1",
                                }
                            ]
                        }
                    }
                ]
            }
        ).encode("utf-8")


def test_gemini_client_generate() -> None:
    with patch("backend.ai_service.services.gemini_client.urlopen", return_value=FakeResponse()):
        result = GeminiClient(
            api_key="test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        ).generate(model="gemini-2.5-flash", prompt="Return SELECT 1")

    assert result == "SELECT 1"
