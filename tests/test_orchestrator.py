"""Tests for the Orchestrator and core components."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


@pytest.fixture
def mock_config():
    cfg = {
        "budget": {
            "daily_limit_tokens": 10000,
            "per_request_max_tokens": 500,
            "curiosity_daily_ops": 5,
            "curiosity_per_op_tokens": 100,
            "warning_threshold": 0.8,
            "hard_stop": True,
            "reset_hour": 0,
        },
        "providers": {
            "primary": "gemini-flash",
            "fallback": "gemini-pro",
            "models": {
                "gemini-flash": {
                    "model_id": "gemini/gemini-2.0-flash",
                    "max_tokens": 500,
                    "temperature": 0.7,
                    "use_for": ["routing", "simple_tasks"],
                },
                "gemini-pro": {
                    "model_id": "gemini/gemini-1.5-pro-latest",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                    "use_for": ["complex_reasoning"],
                },
            },
        },
        "orchestrator": {
            "max_parallel_hypotheses": 3,
            "confidence_threshold": 0.7,
            "auto_prune_below": 0.3,
            "simple_question_threshold": 0.85,
        },
        "memory": {
            "sqlite_path": "./test_data/test.db",
            "vector_store_path": "./test_data/chroma",
            "working_memory_slots": 7,
            "episodic_max_entries": 100,
            "hebbian_learning_rate": 0.1,
            "semantic_decay_rate": 0.01,
            "consolidation_interval_minutes": 30,
        },
    }
    with patch("nexus.config.load_config", return_value=cfg), \
         patch("nexus.config.get", side_effect=lambda k, d=None: {
             "orchestrator.confidence_threshold": 0.7,
             "orchestrator.max_parallel_hypotheses": 3,
             "orchestrator.simple_question_threshold": 0.85,
         }.get(k, d)), \
         patch("nexus.config.data_dir", return_value=Path("./test_data")):
        yield cfg


# ── Agent Registry Tests ──
class TestAgentRegistry:
    @pytest.mark.asyncio
    async def test_register_and_list(self):
        from nexus.core.agent_registry import AgentRegistry
        from nexus.core.agent_base import BaseAgent, AgentMessage, AgentResult, AgentCapability

        class DummyAgent(BaseAgent):
            name = "dummy"
            description = "Test agent"
            capabilities = [AgentCapability.REASONING]

            async def process(self, message, context):
                return AgentResult(content="dummy response", confidence=0.9)

        registry = AgentRegistry()
        agent = DummyAgent()
        registry.register(agent)

        assert len(registry.list_agents()) == 1
        assert registry.get("dummy") is not None
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_rank_for_message(self):
        from nexus.core.agent_registry import AgentRegistry
        from nexus.core.agent_base import BaseAgent, AgentMessage, AgentResult, AgentCapability

        class HighAgent(BaseAgent):
            name = "high"
            description = "High match"
            capabilities = [AgentCapability.CODE]
            def can_handle(self, msg, ctx):
                return 0.9

            async def process(self, message, context):
                return AgentResult(content="high", confidence=0.9)

        class LowAgent(BaseAgent):
            name = "low"
            description = "Low match"
            capabilities = [AgentCapability.WEB]
            def can_handle(self, msg, ctx):
                return 0.2

            async def process(self, message, context):
                return AgentResult(content="low", confidence=0.2)

        registry = AgentRegistry()
        registry.register(HighAgent())
        registry.register(LowAgent())

        msg = AgentMessage(role="user", content="test")
        ranked = registry.rank_for_message(msg, {})
        assert ranked[0][0].name == "high"
        assert ranked[0][1] == 0.9


# ── Three Stream Tests ──
class TestThreeStream:
    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        from nexus.core.three_stream import ThreeStreamProcessor

        processor = ThreeStreamProcessor()

        async def think():
            return "thought"

        async def act():
            return "acted"

        async def remember():
            return "remembered"

        results = await processor.run_parallel(
            think_coro=think(),
            act_coro=act(),
            remember_coro=remember(),
        )
        assert results["think"] == "thought"
        assert results["act"] == "acted"
        assert results["remember"] == "remembered"

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        from nexus.core.three_stream import ThreeStreamProcessor, StreamEvent

        processor = ThreeStreamProcessor()
        queue = processor.subscribe()

        await processor.emit(StreamEvent(
            stream="test", event_type="test_event", content="hello"
        ))

        event = queue.get_nowait()
        assert event.content == "hello"
        assert event.stream == "test"

        processor.unsubscribe(queue)


# ── Verifier Tests ──
class TestVerifier:
    @pytest.mark.asyncio
    async def test_verify_pass(self):
        from nexus.core.verifier import Verifier

        verifier = Verifier(confidence_threshold=0.7)
        mock_llm = AsyncMock(return_value='{"confidence": 0.9, "issues": [], "suggestion": ""}')

        result = await verifier.verify("What is 2+2?", "4", mock_llm)
        assert result.passed is True
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_verify_fail(self):
        from nexus.core.verifier import Verifier

        verifier = Verifier(confidence_threshold=0.7)
        mock_llm = AsyncMock(return_value='{"confidence": 0.3, "issues": ["Wrong"], "suggestion": "Fix it"}')

        result = await verifier.verify("What is 2+2?", "5", mock_llm)
        assert result.passed is False
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_verify_handles_parse_error(self):
        from nexus.core.verifier import Verifier

        verifier = Verifier()
        mock_llm = AsyncMock(return_value="not json at all")

        result = await verifier.verify("Q", "A", mock_llm)
        assert result.passed is True  # Don't block on parse failures


# ── Workflow Engine Tests ──
class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        from nexus.core.workflow_engine import WorkflowEngine, WorkflowNode

        engine = WorkflowEngine()
        results_order = []

        async def step1(**kwargs):
            results_order.append("step1")
            return "result1"

        async def step2(**kwargs):
            results_order.append("step2")
            return "result2"

        engine.add_node(WorkflowNode(id="s1", name="Step 1", handler=step1))
        engine.add_node(WorkflowNode(id="s2", name="Step 2", handler=step2, depends_on=["s1"]))

        results = await engine.execute()
        assert results["s1"] == "result1"
        assert results["s2"] == "result2"
        assert results_order == ["step1", "step2"]

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        from nexus.core.workflow_engine import WorkflowEngine, WorkflowNode

        engine = WorkflowEngine()

        async def step_a(**kwargs):
            await asyncio.sleep(0.01)
            return "A"

        async def step_b(**kwargs):
            await asyncio.sleep(0.01)
            return "B"

        engine.add_node(WorkflowNode(id="a", name="A", handler=step_a))
        engine.add_node(WorkflowNode(id="b", name="B", handler=step_b))

        results = await engine.execute()
        assert results["a"] == "A"
        assert results["b"] == "B"

    @pytest.mark.asyncio
    async def test_failed_dependency_skips(self):
        from nexus.core.workflow_engine import WorkflowEngine, WorkflowNode, NodeStatus

        engine = WorkflowEngine()

        async def fail_step(**kwargs):
            raise ValueError("intentional")

        async def dependent_step(**kwargs):
            return "should not run"

        engine.add_node(WorkflowNode(id="fail", name="Fail", handler=fail_step))
        engine.add_node(WorkflowNode(id="dep", name="Dep", handler=dependent_step, depends_on=["fail"]))

        await engine.execute()
        assert engine._nodes["fail"].status == NodeStatus.FAILED
        assert engine._nodes["dep"].status == NodeStatus.SKIPPED


# ── Message Queue Tests ──
class TestMessageQueue:
    @pytest.mark.asyncio
    async def test_put_and_get(self):
        from nexus.core.message_queue import MessageQueue, QueueItem

        mq = MessageQueue(debounce_ms=0)
        await mq.put(QueueItem(payload="hello", source="test"))
        item = await mq.get()
        assert item.payload == "hello"

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        from nexus.core.message_queue import MessageQueue, QueueItem

        mq = MessageQueue(debounce_ms=0)
        await mq.put(QueueItem(payload="low", priority=1, source="a"))
        await mq.put(QueueItem(payload="high", priority=10, source="b"))

        item = await mq.get()
        assert item.payload == "high"


# ── Common Sense Tests ──
class TestCommonSense:
    def test_greeting_detection(self):
        from nexus.core.common_sense import CommonSenseFilter

        cs = CommonSenseFilter()
        can_answer, response = cs.can_answer_locally("Hello there!")
        assert can_answer is True
        assert "Hello" in response or "Nexus" in response

    def test_math_local(self):
        from nexus.core.common_sense import CommonSenseFilter

        cs = CommonSenseFilter()
        can_answer, response = cs.can_answer_locally("2 + 3")
        assert can_answer is True
        assert "5" in response

    def test_complexity_hint(self):
        from nexus.core.common_sense import CommonSenseFilter

        cs = CommonSenseFilter()
        assert cs.get_complexity_hint("Hello") == "simple"
        assert cs.get_complexity_hint("Write a Python function that implements quicksort") in ("moderate", "complex")

    def test_code_detection(self):
        from nexus.core.common_sense import CommonSenseFilter

        cs = CommonSenseFilter()
        category = cs.get_category("Write a Python function to sort")
        assert category == "coding"
