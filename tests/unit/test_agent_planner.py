import pytest
from accessibility_agent.agent.planner import AgentPlanner
from accessibility_agent.ai.llm_client import LLMResponse

class MockLLMClient:
    def __init__(self, response_text: str, provider: str = "mock"):
        self._response_text = response_text
        self._provider = provider

    @property
    def provider_name(self):
        return self._provider

    async def generate(self, prompt: str, system: str = "") -> LLMResponse:
        return LLMResponse(text=self._response_text, model="mock-model", prompt_tokens=10, completion_tokens=10)


@pytest.mark.asyncio
async def test_planner_disabled_returns_empty():
    mock_llm = MockLLMClient("", provider="disabled")
    planner = AgentPlanner(llm_client=mock_llm)
    assert planner.is_enabled is False
    result = await planner.get_next_interactions("<html></html>")
    assert result == []

@pytest.mark.asyncio
async def test_planner_extracts_selectors_from_json():
    mock_response = '{"selectors": ["#btn1", ".menu"]}'
    mock_llm = MockLLMClient(mock_response, provider="mock")
    planner = AgentPlanner(llm_client=mock_llm)
    
    assert planner.is_enabled is True
    result = await planner.get_next_interactions("<html><button id='btn1'></button></html>")
    assert result == ["#btn1", ".menu"]

@pytest.mark.asyncio
async def test_planner_extracts_selectors_from_markdown_fenced_json():
    mock_response = '```json\n{"selectors": ["#modal-trigger"]}\n```'
    mock_llm = MockLLMClient(mock_response, provider="mock")
    planner = AgentPlanner(llm_client=mock_llm)
    
    result = await planner.get_next_interactions("<html></html>")
    assert result == ["#modal-trigger"]

@pytest.mark.asyncio
async def test_planner_limits_to_5_selectors():
    mock_response = '{"selectors": ["#s1", "#s2", "#s3", "#s4", "#s5", "#s6"]}'
    mock_llm = MockLLMClient(mock_response, provider="mock")
    planner = AgentPlanner(llm_client=mock_llm)
    
    result = await planner.get_next_interactions("<html></html>")
    assert len(result) == 5
    assert result == ["#s1", "#s2", "#s3", "#s4", "#s5"]

@pytest.mark.asyncio
async def test_planner_handles_invalid_json():
    mock_response = 'Here are the selectors: ["#s1"]'
    mock_llm = MockLLMClient(mock_response, provider="mock")
    planner = AgentPlanner(llm_client=mock_llm)
    
    result = await planner.get_next_interactions("<html></html>")
    assert result == []
