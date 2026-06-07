from django.http import HttpResponse

from backend.shared.config import get_settings


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = set(get_settings().cors_origins)

    def __call__(self, request):
        origin = request.headers.get("Origin")
        is_allowed_origin = origin in self.allowed_origins

        if request.method == "OPTIONS" and is_allowed_origin:
            response = HttpResponse(status=200)
        else:
            response = self.get_response(request)

        if is_allowed_origin:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Vary"] = append_vary_header(response.get("Vary"), "Origin")

        return response


def append_vary_header(current_value: str | None, header_name: str) -> str:
    if not current_value:
        return header_name

    headers = [header.strip() for header in current_value.split(",")]
    if header_name not in headers:
        headers.append(header_name)
    return ", ".join(headers)
