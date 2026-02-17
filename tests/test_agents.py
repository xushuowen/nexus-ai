"""Tests for specialist agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nexus.core.agent_base import AgentMessage, AgentCapability


# ── Agent Can-Handle Scoring Tests ──
class TestCoderAgent:
    def test_can_handle_code_request(self):
        from nexus.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        msg = AgentMessage(role="user", content="Write a Python function to sort a list")
        score = agent.can_handle(msg, {})
        assert score > 0.3

    def test_can_handle_non_code(self):
        from nexus.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        msg = AgentMessage(role="user", content="What's the weather today?")
        score = agent.can_handle(msg, {})
        assert score < 0.3

    @pytest.mark.asyncio
    async def test_process_with_llm(self):
        from nexus.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="```python\ndef sort_list(lst):\n    return sorted(lst)\n```")
        agent.set_llm(mock_llm)

        msg = AgentMessage(role="user", content="Write a sort function")
        result = await agent.process(msg, {})
        assert "sorted" in result.content
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_process_without_llm(self):
        from nexus.agents.coder_agent import CoderAgent

        agent = CoderAgent()
        msg = AgentMessage(role="user", content="Write code")
        result = await agent.process(msg, {})
        assert result.confidence == 0.0


class TestResearchAgent:
    def test_can_handle_research(self):
        from nexus.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        msg = AgentMessage(role="user", content="Search for the latest news about AI")
        score = agent.can_handle(msg, {})
        assert score > 0.3

    def test_capabilities(self):
        from nexus.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        assert AgentCapability.RESEARCH in agent.capabilities


class TestReasoningAgent:
    def test_can_handle_reasoning(self):
        from nexus.agents.reasoning_agent import ReasoningAgent

        agent = ReasoningAgent()
        msg = AgentMessage(role="user", content="Why does water boil at 100 degrees? Analyze step by step.")
        score = agent.can_handle(msg, {})
        assert score > 0.3

    @pytest.mark.asyncio
    async def test_process(self):
        from nexus.agents.reasoning_agent import ReasoningAgent

        agent = ReasoningAgent()
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="Step 1: Water molecules gain energy... high confidence conclusion.")
        agent.set_llm(mock_llm)

        msg = AgentMessage(role="user", content="Why does water boil?")
        result = await agent.process(msg, {})
        assert result.confidence > 0.5


class TestKnowledgeAgent:
    @pytest.mark.asyncio
    async def test_with_memory_results(self):
        from nexus.agents.knowledge_agent import KnowledgeAgent

        agent = KnowledgeAgent()
        mock_memory = MagicMock()
        mock_memory.search = AsyncMock(return_value=[
            {"source": "fts", "content": "AI stands for Artificial Intelligence"}
        ])
        agent.set_dependencies(mock_memory, None)

        msg = AgentMessage(role="user", content="What do you know about AI?")
        result = await agent.process(msg, {})
        assert "Artificial Intelligence" in result.content
        assert result.confidence > 0.5

    @pytest.mark.asyncio
    async def test_without_memory(self):
        from nexus.agents.knowledge_agent import KnowledgeAgent

        agent = KnowledgeAgent()
        msg = AgentMessage(role="user", content="Random question")
        result = await agent.process(msg, {})
        assert result.confidence < 0.5


class TestOptimizerAgent:
    @pytest.mark.asyncio
    async def test_status_report(self):
        from nexus.agents.optimizer_agent import OptimizerAgent

        agent = OptimizerAgent()
        mock_budget = MagicMock()
        mock_budget.get_status.return_value = {
            "tokens_used": 500,
            "daily_limit": 10000,
            "tokens_remaining": 9500,
            "usage_ratio": 0.05,
            "request_count": 10,
            "curiosity_ops_remaining": 5,
        }
        mock_memory = MagicMock()
        mock_memory.working = MagicMock()
        mock_memory.working.size = 3
        mock_memory.fts = MagicMock()
        mock_memory.fts.count = AsyncMock(return_value=42)
        mock_memory.vector = MagicMock()
        mock_memory.vector.count = AsyncMock(return_value=10)

        agent.set_dependencies(mock_budget, mock_memory)

        msg = AgentMessage(role="user", content="Show system status")
        result = await agent.process(msg, {})
        assert "500" in result.content
        assert "10,000" in result.content or "10000" in result.content


class TestShellAgent:
    def test_can_handle(self):
        from nexus.agents.shell_agent import ShellAgent

        agent = ShellAgent()
        msg = AgentMessage(role="user", content="Run the command: ls -la")
        score = agent.can_handle(msg, {})
        assert score > 0.3

    def test_safety_check(self):
        from nexus.agents.shell_agent import ShellAgent

        agent = ShellAgent()
        agent._blocked_commands = ["rm -rf /"]
        assert agent._is_safe("ls -la") is True
        assert agent._is_safe("rm -rf /") is False


class TestWebAgent:
    def test_can_handle_url(self):
        from nexus.agents.web_agent import WebAgent

        agent = WebAgent()
        msg = AgentMessage(role="user", content="Fetch https://example.com")
        score = agent.can_handle(msg, {})
        assert score > 0.5

    def test_can_handle_no_url(self):
        from nexus.agents.web_agent import WebAgent

        agent = WebAgent()
        msg = AgentMessage(role="user", content="Tell me a joke")
        score = agent.can_handle(msg, {})
        assert score < 0.3
