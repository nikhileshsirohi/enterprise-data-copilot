import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_package_defines_react_tailwind_vite_stack() -> None:
    package_json = json.loads((FRONTEND / "package.json").read_text())

    assert package_json["scripts"]["dev"] == "vite --host 127.0.0.1 --port 5173"
    assert "react" in package_json["dependencies"]
    assert "lucide-react" in package_json["dependencies"]
    assert "typescript" in package_json["devDependencies"]
    assert "vite" in package_json["devDependencies"]
    assert "tailwindcss" in package_json["devDependencies"]


def test_frontend_api_client_targets_existing_ai_endpoints() -> None:
    api_source = (FRONTEND / "src" / "api.ts").read_text()

    assert "http://127.0.0.1:8001/api/v1" in api_source
    assert "http://127.0.0.1:8000/api/v1" in api_source
    assert "/auth/login/" in api_source
    assert '"/auth/me/"' in api_source
    assert '"/ask/"' in api_source
    assert '"/chat/sessions"' in api_source
    assert "`/chat/sessions/${sessionId}`" in api_source


def test_frontend_chat_ui_includes_required_workspace_controls() -> None:
    app_source = (FRONTEND / "src" / "App.tsx").read_text()

    assert "Login" in app_source
    assert "Staff" in app_source
    assert "Super User" in app_source
    assert "Dashboard" in app_source
    assert "Data Explorer" in app_source
    assert "Documents" in app_source
    assert "Audit Logs" in app_source
    assert "SQL Review" in app_source
    assert "Available stock of material MAT0006" in app_source
    assert "What is the reimbursement limit for meals?" in app_source
    assert "Answer details" in app_source
    assert "Answer source" in app_source
    assert "Generated SQL" in app_source
    assert "Policy sources and citations" in app_source
