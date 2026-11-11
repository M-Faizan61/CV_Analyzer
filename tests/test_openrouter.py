"""OpenRouter is replaced by a fake here, so these tests need no key and no internet."""
import json
from unittest.mock import Mock, patch

import pytest
import requests

from helpers import skill, typed_cv
from models.schemas import CvExtraction, Requirement
from services import openrouter_client, pipeline
from services.job_parser import parse_job_with_ai
from services.openrouter_client import OpenRouterError, request_json
from services.pipeline import AiOptions

AI = AiOptions(api_key="secret-key", model="openrouter/free")
CV = "Ali Raza\nSKILLS\nPython: 3 years\nBuilt a plugin for reports."


def reply(content, status=200, finish_reason="stop"):
    response = Mock(status_code=status)
    response.json.return_value = {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}
    return response


def json_reply(**data):
    return reply(json.dumps(data))


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(openrouter_client.time, "sleep", lambda seconds: None)


def test_request_format_matches_openrouter():
    with patch("services.openrouter_client.requests.post", return_value=json_reply(name="Ali")) as post:
        request_json(CvExtraction, "Read", {"cv": "text"}, "secret-key", "openai/gpt-4o-mini")
    call = post.call_args
    assert call.args[0] == "https://openrouter.ai/api/v1/chat/completions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert call.kwargs["json"]["model"] == "openai/gpt-4o-mini"
    assert call.kwargs["json"]["response_format"] == {"type": "json_object"}
    assert "secret-key" not in str(call.kwargs["json"])
    assert "untrusted" in call.kwargs["json"]["messages"][0]["content"]


def test_key_from_env_is_used_when_none_is_typed(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    with patch("services.openrouter_client.requests.post", return_value=json_reply()) as post:
        request_json(CvExtraction, "Read", {})
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer env-key"


def test_missing_key_gives_a_clear_message():
    with pytest.raises(OpenRouterError, match="API key"):
        request_json(CvExtraction, "Read", {})


def test_json_inside_code_fences_is_accepted():
    with patch("services.openrouter_client.requests.post", return_value=reply('```json\n{"name": "Ali"}\n```')):
        assert request_json(CvExtraction, "Read", {}, "key").name == "Ali"


@pytest.mark.parametrize("status,text,fatal", [
    (401, "API key", True),
    (402, "credits", True),
    (404, "not available", True),
    (429, "rate limit", False),
    (503, "busy", False),
])
def test_errors_are_clear_and_never_leak_secrets(status, text, fatal):
    response = Mock(status_code=status, text="secret-key and CV text")
    with patch("services.openrouter_client.requests.post", return_value=response):
        with pytest.raises(OpenRouterError) as error:
            request_json(CvExtraction, "Read", {}, "secret-key")
    assert text in str(error.value)
    assert error.value.fatal is fatal
    assert "secret-key" not in str(error.value)


def test_error_inside_a_200_reply_is_caught():
    response = Mock(status_code=200)
    response.json.return_value = {"error": {"code": 402, "message": "No credits"}}
    with patch("services.openrouter_client.requests.post", return_value=response):
        with pytest.raises(OpenRouterError, match="credits"):
            request_json(CvExtraction, "Read", {}, "key")


def test_busy_model_is_retried():
    responses = [Mock(status_code=503), json_reply(name="Ali")]
    with patch("services.openrouter_client.requests.post", side_effect=responses) as post:
        assert request_json(CvExtraction, "Read", {}, "key").name == "Ali"
    assert post.call_count == 2


def test_badly_formatted_reply_is_retried_then_reported():
    with patch("services.openrouter_client.requests.post", return_value=reply("not json")) as post:
        with pytest.raises(OpenRouterError, match="expected format"):
            request_json(CvExtraction, "Read", {}, "key")
    assert post.call_count == openrouter_client.MAX_ATTEMPTS


def test_cut_off_reply_is_reported():
    with patch("services.openrouter_client.requests.post", return_value=reply("{", finish_reason="length")):
        with pytest.raises(OpenRouterError, match="cut off"):
            request_json(CvExtraction, "Read", {}, "key")


@pytest.mark.parametrize("error,text", [
    (requests.exceptions.ConnectTimeout("secret"), "too long"),
    (requests.exceptions.SSLError("secret"), "secure connection"),
    (requests.exceptions.ConnectionError("secret"), "internet"),
])
def test_network_problems_are_explained(error, text):
    with patch("services.openrouter_client.requests.post", side_effect=error):
        with pytest.raises(OpenRouterError) as raised:
            request_json(CvExtraction, "Read", {}, "key")
    assert text in str(raised.value)
    assert "secret" not in str(raised.value)


def test_invalid_model_name_is_refused_without_a_request():
    with patch("services.openrouter_client.requests.post") as post:
        with pytest.raises(OpenRouterError, match="not valid"):
            request_json(CvExtraction, "Read", {}, "key", "bad model!")
    post.assert_not_called()


# --- The AI finds evidence, Python decides ---
def run_ai(requirement, **ai_reply):
    with patch("services.openrouter_client.requests.post", return_value=json_reply(**ai_reply)):
        return pipeline.analyze_cv(typed_cv(CV), [requirement], AI)


def other_requirement():
    return Requirement(id="R1", text="Plugin development required", kind="other")


def test_ai_evidence_with_a_real_quote_is_accepted():
    result = run_ai(other_requirement(), findings=[{"requirement_id": "R1", "answer": "found", "quote": "Built a plugin for reports."}])
    assert result.findings[0].status == "MET"
    assert result.outcome == "SHORTLISTED"


def test_quote_with_different_spacing_still_counts():
    quote = "Built   a plugin\nfor reports."
    assert run_ai(other_requirement(), findings=[{"requirement_id": "R1", "answer": "found", "quote": quote}]).findings[0].status == "MET"


def test_made_up_ai_quote_cannot_shortlist_anyone():
    result = run_ai(other_requirement(), findings=[{"requirement_id": "R1", "answer": "found", "quote": "Led the plugin team for ten years"}])
    assert result.findings[0].status == "REVIEW"
    assert result.outcome == "NEEDS_REVIEW"


def test_ai_cannot_override_the_skill_rules():
    """GitHub does not prove Git, even when the AI says it does."""
    cv = "Ali Raza\nGitHub: example profile with more text"
    with patch("services.openrouter_client.requests.post",
               return_value=json_reply(findings=[{"requirement_id": "R1", "answer": "found", "quote": "GitHub: example profile"}])):
        result = pipeline.analyze_cv(typed_cv(cv), [skill("git")], AI)
    assert result.findings[0].status == "REVIEW"
    assert result.outcome == "NEEDS_REVIEW"


def test_ai_cannot_prove_an_activity_when_the_named_skill_is_missing():
    """CMS plugins do not prove WordPress plugins, even with a real quote."""
    requirement = Requirement(id="R1", text="WordPress plugin development required", kind="other", skills="wordpress")
    cv = "Ali Raza\nBuilt CMS plugins for clients over several years"
    with patch("services.openrouter_client.requests.post",
               return_value=json_reply(findings=[{"requirement_id": "R1", "answer": "found", "quote": "Built CMS plugins for clients"}])):
        result = pipeline.analyze_cv(typed_cv(cv), [requirement], AI)
    assert result.findings[0].status == "REVIEW"
    assert result.outcome == "NEEDS_REVIEW"


def test_ai_details_are_used_only_if_they_appear_in_the_cv():
    result = run_ai(skill("python"), name="Invented Person", summary="A Python developer.", skills=["Python", "Kubernetes"])
    assert result.profile.name == "Ali Raza"
    assert result.profile.summary == "A Python developer."
    assert "kubernetes" not in result.profile.skills


def test_ai_failure_on_one_cv_falls_back_to_rules_and_says_so():
    with patch("services.openrouter_client.requests.post", return_value=reply("not json")):
        result = pipeline.analyze_cv(typed_cv(CV), [skill("python")], AI)
    assert result.outcome == "SHORTLISTED"
    assert any("manual rules" in warning for warning in result.warnings)


def test_bad_key_stops_the_whole_batch():
    with patch("services.openrouter_client.requests.post", return_value=Mock(status_code=401)):
        with pytest.raises(OpenRouterError, match="API key"):
            pipeline.analyze_batch([typed_cv(CV)], [skill("python")], AI)


def test_manual_method_never_calls_the_api():
    with patch("services.openrouter_client.requests.post") as post:
        pipeline.read_requirements("Python required")
        pipeline.analyze_cv(typed_cv(CV), [skill("python")])
    post.assert_not_called()


# --- Reading a job description with AI ---
def test_ai_job_parsing_applies_the_safety_rules():
    job = "Python required\nAge under 30"
    items = [
        {"text": "Python required", "importance": "Mandatory", "kind": "skill", "skills": "Python", "operator": "all"},
        {"text": "Age under 30", "importance": "mandatory", "kind": "skill", "skills": "age"},
        {"text": "Ten years of Rust", "importance": "mandatory", "kind": "skill", "skills": "rust"},
    ]
    with patch("services.openrouter_client.requests.post", return_value=json_reply(requirements=items)):
        requirements = parse_job_with_ai(job, "key")
    assert [item.id for item in requirements] == ["R1", "R2", "R3"]
    assert requirements[0].importance == "mandatory"
    assert (requirements[1].kind, requirements[1].importance) == ("personal", "ignore")
    assert requirements[2].importance == "ignore"  # the job does not say this, so it cannot decide anything
