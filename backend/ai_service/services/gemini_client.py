import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str, base_url: str, timeout_seconds: int = 120) -> None:
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is not configured.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, model: str, prompt: str) -> str:
        request = Request(
            url=f"{self.base_url}/models/{model}:generateContent",
            data=json.dumps(
                {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": prompt}],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0,
                    },
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8")
            raise GeminiError(f"Gemini API error {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise GeminiError(f"Gemini is not reachable: {exc}") from exc

        return self._extract_text(payload)

    def _extract_text(self, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise GeminiError(f"Gemini returned no candidates: {payload}")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        generated_text = "\n".join(text_parts).strip()
        if not generated_text:
            raise GeminiError(f"Gemini returned an empty text response: {payload}")
        return generated_text
