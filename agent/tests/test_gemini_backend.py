"""Backend de Gemini: API key de AI Studio (local) o Vertex AI con la cuenta de servicio (Cloud Run)."""

from sofia_agent.config import Settings


def _settings(**env) -> Settings:
    return Settings.model_validate({"SOFIA_LLM_MODE": "auto", **env})


def test_ai_studio_uses_api_key():
    s = _settings(GEMINI_API_KEY="k")
    assert s.use_gemini
    assert s.gemini_client_kwargs == {"google_api_key": "k"}


def test_vertex_uses_project_and_location_without_api_key():
    s = _settings(GEMINI_BACKEND="vertex", GOOGLE_CLOUD_PROJECT="sofia", GOOGLE_CLOUD_LOCATION="us-central1")
    assert s.use_gemini
    assert s.gemini_client_kwargs == {"vertexai": True, "project": "sofia", "location": "us-central1"}


def test_vertex_without_project_falls_back_to_rules():
    s = _settings(GEMINI_BACKEND="vertex")
    assert not s.use_gemini
    assert s.gemini_client_kwargs == {}
