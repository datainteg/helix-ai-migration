"""Tests for Prompt 7: PydanticAI-compatible structured output runtime."""

import json

import pytest
from pydantic import BaseModel, ValidationError

from agents.runtime.llm_router import build_mock_agent_prompt, route_llm_call
from agents.runtime.structured_output import (
    build_mock_agent_response,
    parse_router_result,
    parse_structured_output,
    safe_extract_json,
)
from agents.runtime.types import LLMRouterResult, StructuredOutputResult


# â”€â”€ Test models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _TestOutput(BaseModel):
    summary: str
    score: float = 0.0


class _TestNestedOutput(BaseModel):
    title: str
    items: list[str] = []


# â”€â”€ safe_extract_json â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestSafeExtractJson:
    def test_plain_json_object(self):
        assert safe_extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_fenced_json_block(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        assert safe_extract_json(text) == '{"key": "value"}'

    def test_fenced_block_no_language(self):
        text = '```\n{"key": "value"}\n```'
        assert safe_extract_json(text) == '{"key": "value"}'

    def test_json_array(self):
        assert safe_extract_json('[1, 2, 3]') == '[1, 2, 3]'

    def test_no_json_returns_none(self):
        assert safe_extract_json("Just some plain text.") is None

    def test_empty_input(self):
        assert safe_extract_json("") is None
        assert safe_extract_json("   ") is None

    def test_json_within_text(self):
        text = "The answer is: {'nested': true} and more text."
        result = safe_extract_json(text)
        assert result is not None
        assert "nested" in result

    def test_malformed_json_still_extracted(self):
        text = '```json\n{broken: true,\n```'
        result = safe_extract_json(text)
        assert result is not None


# â”€â”€ parse_structured_output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestParseStructuredOutput:
    def test_valid_json_parses(self):
        result = parse_structured_output(
            '{"summary": "test", "score": 0.9}',
            _TestOutput,
        )
        assert result.success is True
        assert isinstance(result.parsed, _TestOutput)
        assert result.parsed.summary == "test"
        assert result.parsed.score == 0.9

    def test_fenced_json_parses(self):
        result = parse_structured_output(
            '```json\n{"summary": "fenced", "score": 0.5}\n```',
            _TestOutput,
        )
        assert result.success is True
        assert result.parsed.summary == "fenced"

    def test_malformed_json_returns_error(self):
        result = parse_structured_output(
            '{broken json!!!!',
            _TestOutput,
        )
        assert result.success is False
        assert any("No JSON found" in e or "JSON decode" in e for e in result.errors)

    def test_valid_json_wrong_schema_returns_error(self):
        result = parse_structured_output(
            '{"wrong_field": 123}',
            _TestOutput,
        )
        assert result.success is False
        assert any("Validation error" in e for e in result.errors)

    def test_empty_input_returns_error(self):
        result = parse_structured_output("", _TestOutput)
        assert result.success is False

    def test_no_json_in_text_returns_error(self):
        result = parse_structured_output("No JSON here at all.", _TestOutput)
        assert result.success is False

    def test_preserves_raw_text(self):
        raw = '{"summary": "keep me", "score": 1.0}'
        result = parse_structured_output(raw, _TestOutput)
        assert result.raw_text == raw

    def test_metadata_includes_extracted_json(self):
        result = parse_structured_output(
            '{"summary": "meta", "score": 0.3}',
            _TestOutput,
        )
        assert "extracted_json" in result.metadata


# â”€â”€ route_llm_call â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestRouteLlmCall:
    def test_mock_mode_returns_provided_response(self):
        result = route_llm_call(
            agent_name="business_analyst",
            prompt="Test prompt",
            mock_response='{"summary": "mock"}',
        )
        assert isinstance(result, LLMRouterResult)
        assert result.raw_text == '{"summary": "mock"}'
        assert result.mode == "mock"
        assert result.provider_name == "mock"
        assert result.agent_name == "business_analyst"

    def test_mock_mode_without_response_returns_empty(self):
        result = route_llm_call(
            agent_name="architect",
            prompt="Test prompt",
        )
        assert result.raw_text == ""
        assert result.mode == "mock"

    def test_resolves_model_per_agent(self):
        result = route_llm_call(
            agent_name="business_analyst",
            prompt="Test",
            mock_response="x",
        )
        assert result.model_name == "mock-gpt-4.1"

        result = route_llm_call(
            agent_name="architect",
            prompt="Test",
            mock_response="x",
        )
        assert result.model_name == "mock-claude-3-opus"

    def test_never_exposes_api_keys(self):
        result = route_llm_call(
            agent_name="business_analyst",
            prompt="sk-very-secret-key",
            mock_response="ok",
        )
        assert "sk-" not in result.provider_name
        assert result.provider_name == "mock"


# â”€â”€ build_mock_agent_prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestBuildMockAgentPrompt:
    def test_builds_prompt_with_agent_metadata(self):
        prompt = build_mock_agent_prompt("business_analyst", "Migrate CRM data")
        assert "Mary" in prompt
        assert "Business Analyst" in prompt
        assert "Migrate CRM data" in prompt

    def test_builds_prompt_for_all_registered_agents(self):
        for agent_key in ["business_analyst", "architect", "pm", "data_engineer"]:
            prompt = build_mock_agent_prompt(agent_key, "Test requirement")
            assert len(prompt) > 50
            assert "Test requirement" in prompt


# â”€â”€ build_mock_agent_response â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestBuildMockAgentResponse:
    def test_builds_valid_mock_for_known_schema(self):
        from agents.bmad.schemas import BusinessAnalystOutput

        result = build_mock_agent_response(
            "business_analyst",
            BusinessAnalystOutput,
        )
        assert result.success is True
        assert isinstance(result.parsed, BusinessAnalystOutput)
        assert result.parsed.summary is not None
        assert len(result.parsed.business_goals) >= 1

    def test_builds_mock_for_architect(self):
        from agents.bmad.schemas import ArchitectOutput

        result = build_mock_agent_response("architect", ArchitectOutput)
        assert result.success is True
        assert isinstance(result.parsed, ArchitectOutput)

    def test_builds_mock_for_approval_gate(self):
        from agents.bmad.schemas import ApprovalGateOutput

        result = build_mock_agent_response("architect", ApprovalGateOutput)
        assert result.success is True
        assert result.parsed.approval_required is True

    def test_mock_uses_agent_name_in_summary(self):
        from agents.bmad.schemas import BusinessAnalystOutput

        result = build_mock_agent_response(
            "business_analyst",
            BusinessAnalystOutput,
        )
        assert "Mary" in result.parsed.summary


# â”€â”€ parse_router_result â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestParseRouterResult:
    def test_parses_router_result(self):
        router_result = LLMRouterResult(
            raw_text='{"summary": "from router", "score": 0.99}',
            provider_name="mock",
            model_name="mock-gpt-4.1",
            agent_name="ba",
            mode="mock",
        )
        result = parse_router_result(router_result, _TestOutput)
        assert result.success is True
        assert result.parsed.summary == "from router"
        assert result.metadata["router_mode"] == "mock"
        assert result.metadata["router_provider"] == "mock"


# â”€â”€ Error path coverage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestErrorPaths:
    def test_router_result_with_invalid_json(self):
        router_result = LLMRouterResult(
            raw_text="not json at all",
            provider_name="mock",
            model_name="mock-gpt-4.1",
            agent_name="ba",
            mode="mock",
        )
        result = parse_router_result(router_result, _TestOutput)
        assert result.success is False

    def test_mock_response_for_unknown_agent_raises_keyerror(self):
        """Unknown agent keys should raise KeyError â€” callers must validate agent keys."""
        from agents.bmad.schemas import BusinessAnalystOutput

        with pytest.raises(KeyError):
            build_mock_agent_response("nonexistent_agent", BusinessAnalystOutput)

    def test_json_with_trailing_comma_fails_gracefully(self):
        result = parse_structured_output(
            '{"summary": "test",}',
            _TestOutput,
        )
        assert result.success is False

