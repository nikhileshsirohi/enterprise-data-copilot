import json
from urllib.error import URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, model: str, prompt: str) -> str:
        request = Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(
                {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                    },
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise OllamaError(f"Ollama is not reachable: {exc}") from exc

        generated_text = payload.get("response")
        if not generated_text:
            raise OllamaError("Ollama returned an empty response.")

        return generated_text.strip()

    def embed(self, model: str, text: str) -> list[float]:
        request = Request(
            url=f"{self.base_url}/api/embeddings",
            data=json.dumps(
                {
                    "model": model,
                    "prompt": text,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise OllamaError(f"Ollama embedding endpoint is not reachable: {exc}") from exc

        embedding = payload.get("embedding")
        if not embedding:
            raise OllamaError("Ollama returned an empty embedding response.")

        return [float(value) for value in embedding]
