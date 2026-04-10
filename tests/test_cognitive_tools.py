"""Tests for the consolidated macro-tools.

[AUTONOMY x CRUCIBLE] — Tests for all 8 macro-tools.
"""

import collections
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from cognitive.tools.analyze import analyze_workflow
from cognitive.tools.mutate import mutate_workflow
from cognitive.tools.query import query_environment
from cognitive.tools.dependencies import manage_dependencies
from cognitive.tools.execute import execute_workflow, ExecutionStatus, ExecutionResult
from cognitive.tools.compose import compose_workflow
from cognitive.tools.series import generate_series, SeriesConfig
from cognitive.tools.research import autoresearch, AutoresearchConfig
from cognitive.core.graph import CognitiveGraphEngine
from cognitive.transport.schema_cache import SchemaCache


# ---------------------------------------------------------------------------
# WebSocket mock helper for TestExecuteWorkflow
# ---------------------------------------------------------------------------


class _MockWS:
    """Minimal WebSocket mock matching websockets.sync.client API.

    Yields pre-built JSON message strings via recv(timeout=...). When the
    message queue is empty, recv() raises TimeoutError to simulate the
    real client's no-data-within-timeout behavior. Acts as its own
    context manager.
    """

    def __init__(self, messages: list[str] | None = None):
        self._messages: collections.deque = collections.deque(messages or [])
        self.recv_bufsize = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def recv(self, timeout=None):
        if not self._messages:
            raise TimeoutError("no more mock messages")
        return self._messages.popleft()


def _make_ws_messages(prompt_id: str = "test_prompt", with_progress: bool = False) -> list[str]:
    """Build a typical happy-path WS event sequence ending in completion."""
    msgs = [
        json.dumps({"type": "execution_start", "data": {"prompt_id": prompt_id}}),
        json.dumps({"type": "executing", "data": {"node": "1", "prompt_id": prompt_id}}),
    ]
    if with_progress:
        msgs.append(json.dumps({
            "type": "progress",
            "data": {"value": 5, "max": 10, "prompt_id": prompt_id},
        }))
    msgs.extend([
        json.dumps({"type": "executed", "data": {"node": "1", "prompt_id": prompt_id}}),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": prompt_id}}),
    ])
    return msgs


def _mock_post_ok(prompt_id: str = "test_prompt"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"prompt_id": prompt_id}
    return resp


def _mock_history_with_image(prompt_id: str, filename: str = "test.png"):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        prompt_id: {
            "outputs": {
                "6": {"images": [{"filename": filename, "subfolder": ""}]},
            },
        },
    }
    return resp


def _mock_history_empty(prompt_id: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {prompt_id: {"outputs": {}}}
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_workflow():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a landscape", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly", "clip": ["1", 1]}},
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42, "steps": 20, "cfg": 7.5,
                "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0], "positive": ["2", 0],
                "negative": ["3", 0], "latent_image": ["5", 0],
            },
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
    }


@pytest.fixture
def engine(sample_workflow):
    return CognitiveGraphEngine(sample_workflow)


@pytest.fixture
def schema_cache():
    cache = SchemaCache()
    cache.refresh({
        "KSampler": {
            "input": {
                "required": {
                    "steps": ["INT", {"default": 20, "min": 1, "max": 10000}],
                    "cfg": ["FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0}],
                    "sampler_name": [["euler", "dpmpp_2m"], {}],
                },
            },
            "output": ["LATENT"],
        },
    })
    return cache


# ---------------------------------------------------------------------------
# analyze_workflow
# ---------------------------------------------------------------------------

class TestAnalyzeWorkflow:

    def test_basic_analysis(self, sample_workflow):
        result = analyze_workflow(sample_workflow)
        assert result.node_count == 6
        assert "KSampler" in result.node_types
        assert len(result.connections) > 0
        assert len(result.editable_fields) > 0

    def test_classification_txt2img(self, sample_workflow):
        result = analyze_workflow(sample_workflow)
        assert result.classification == "txt2img"

    def test_model_family_detection(self, sample_workflow):
        result = analyze_workflow(sample_workflow)
        assert result.model_family == "SD1.5"

    def test_summary_present(self, sample_workflow):
        result = analyze_workflow(sample_workflow)
        assert "txt2img" in result.summary
        assert "6 nodes" in result.summary

    def test_schema_validation(self, sample_workflow, schema_cache):
        # Inject invalid value
        sample_workflow["4"]["inputs"]["sampler_name"] = "bad_sampler"
        result = analyze_workflow(sample_workflow, schema_cache=schema_cache)
        assert result.is_valid is False
        assert len(result.validation_errors) > 0

    def test_empty_workflow(self):
        result = analyze_workflow({})
        assert result.node_count == 0

    def test_sdxl_detection(self):
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl-base.safetensors"}},
        }
        result = analyze_workflow(wf)
        assert result.model_family == "SDXL"


# ---------------------------------------------------------------------------
# mutate_workflow
# ---------------------------------------------------------------------------

class TestMutateWorkflow:

    def test_valid_mutation(self, engine):
        result = mutate_workflow(engine, {"4": {"steps": 30}})
        assert result.success is True
        assert len(result.changes) == 1
        assert result.delta_layer_id != ""

    def test_schema_validated_mutation(self, engine, schema_cache):
        result = mutate_workflow(
            engine, {"4": {"sampler_name": "bad"}}, schema_cache=schema_cache,
        )
        assert result.success is False
        assert len(result.validation_errors) > 0

    def test_valid_with_schema(self, engine, schema_cache):
        result = mutate_workflow(
            engine, {"4": {"sampler_name": "euler"}}, schema_cache=schema_cache,
        )
        assert result.success is True

    def test_multi_node_mutation(self, engine):
        result = mutate_workflow(engine, {
            "4": {"steps": 30, "cfg": 5.0},
            "2": {"text": "new prompt"},
        })
        assert result.success is True
        assert len(result.changes) == 3


# ---------------------------------------------------------------------------
# query_environment
# ---------------------------------------------------------------------------

class TestQueryEnvironment:

    def test_full_snapshot(self):
        snap = query_environment(
            system_stats={"devices": [{"name": "RTX 4090", "vram_total": 25769803776, "vram_free": 20000000000}]},
            queue_info={"queue_running": [1], "queue_pending": [2, 3]},
            node_packs=["ComfyUI-Manager", "ComfyUI-Impact-Pack"],
            models={"checkpoints": ["v1-5.safetensors"]},
        )
        assert snap.comfyui_running is True
        assert snap.gpu_name == "RTX 4090"
        assert snap.vram_total_mb > 0
        assert snap.queue_running == 1
        assert snap.queue_pending == 2
        assert len(snap.installed_node_packs) == 2

    def test_empty_snapshot(self):
        snap = query_environment()
        assert snap.comfyui_running is False
        assert snap.gpu_name == ""

    def test_with_schema_cache(self, schema_cache):
        snap = query_environment(schema_cache=schema_cache)
        assert snap.schema_cached is True
        assert snap.node_count == 1


# ---------------------------------------------------------------------------
# manage_dependencies
# ---------------------------------------------------------------------------

class TestManageDependencies:

    def test_install_action(self):
        result = manage_dependencies("install", "ComfyUI-Impact-Pack")
        assert result.success is True
        assert result.action == "install"

    def test_invalid_action(self):
        result = manage_dependencies("delete", "some-pack")
        assert result.success is False

    def test_schema_invalidation(self, schema_cache):
        result = manage_dependencies("install", "pack", schema_cache=schema_cache)
        assert result.schema_invalidated is True


# ---------------------------------------------------------------------------
# execute_workflow
# ---------------------------------------------------------------------------

class TestExecuteWorkflow:

    # ─── Early-failure branches (no network, no WS) ─────────────────

    def test_empty_workflow(self):
        result = execute_workflow({})
        assert result.status == ExecutionStatus.FAILED
        assert "Empty" in result.error

    def test_no_nodes_workflow(self):
        result = execute_workflow({"metadata": "not a node"})
        assert result.status == ExecutionStatus.FAILED
        assert "No nodes" in result.error

    # ─── Real-execution paths (mocked POST + WS + history) ──────────

    def _patch_stack(self, ws_messages, post_resp=None, history_resp=None, prompt_id="test_prompt"):
        """Build the standard 3-patch stack: connect, post, get."""
        if post_resp is None:
            post_resp = _mock_post_ok(prompt_id)
        if history_resp is None:
            history_resp = _mock_history_with_image(prompt_id)

        mock_ws = _MockWS(ws_messages)

        mock_http_client = MagicMock()
        mock_http_client.post.return_value = post_resp
        mock_http_client.get.return_value = history_resp
        mock_http_cm = MagicMock()
        mock_http_cm.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_cm.__exit__ = MagicMock(return_value=False)

        return (
            patch("cognitive.tools.execute.websockets.sync.client.connect",
                  return_value=mock_ws),
            patch("cognitive.tools.execute.httpx.Client", return_value=mock_http_cm),
            mock_ws,
            mock_http_client,
        )

    def test_execute_happy_path(self, sample_workflow):
        ws_patch, http_patch, _, _ = self._patch_stack(_make_ws_messages())
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.COMPLETED
        assert result.prompt_id == "test_prompt"
        assert result.output_filenames == ["test.png"]
        assert result.success is True

    def test_execute_with_progress_callback(self, sample_workflow):
        events = []
        ws_patch, http_patch, _, _ = self._patch_stack(
            _make_ws_messages(with_progress=True)
        )
        with ws_patch, http_patch:
            result = execute_workflow(
                sample_workflow,
                on_progress=lambda e: events.append(e),
                base_url="http://mock:8188",
            )
        assert result.status == ExecutionStatus.COMPLETED
        assert len(events) == 1
        assert events[0].progress_pct == 50.0

    def test_execute_on_complete_called_once(self, sample_workflow):
        called = []
        ws_patch, http_patch, _, _ = self._patch_stack(_make_ws_messages())
        with ws_patch, http_patch:
            execute_workflow(
                sample_workflow,
                on_complete=lambda r: called.append(r),
                base_url="http://mock:8188",
            )
        assert len(called) == 1
        assert called[0].status == ExecutionStatus.COMPLETED

    def test_execute_no_callbacks(self, sample_workflow):
        ws_patch, http_patch, _, _ = self._patch_stack(_make_ws_messages())
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.COMPLETED

    def test_execute_comfyui_unreachable(self, sample_workflow):
        # WS connect succeeds, POST raises ConnectError
        mock_ws = _MockWS([])
        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_http_cm = MagicMock()
        mock_http_cm.__enter__ = MagicMock(return_value=mock_http_client)
        mock_http_cm.__exit__ = MagicMock(return_value=False)
        with patch("cognitive.tools.execute.websockets.sync.client.connect",
                   return_value=mock_ws), \
             patch("cognitive.tools.execute.httpx.Client", return_value=mock_http_cm):
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.FAILED
        assert "not reachable" in result.error

    def test_execute_validation_errors(self, sample_workflow):
        bad_resp = MagicMock()
        bad_resp.status_code = 400
        bad_resp.json.return_value = {
            "node_errors": {
                "3": {
                    "class_type": "KSampler",
                    "errors": [{"message": "cfg out of range"}],
                },
            },
        }
        bad_resp.text = "validation failed"
        ws_patch, http_patch, _, _ = self._patch_stack(
            _make_ws_messages(), post_resp=bad_resp,
        )
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.FAILED
        assert "Validation errors" in result.error
        assert "cfg out of range" in result.error

    def test_execute_post_no_prompt_id(self, sample_workflow):
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"prompt_id": ""}
        ws_patch, http_patch, _, _ = self._patch_stack(
            _make_ws_messages(), post_resp=bad_resp,
        )
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.FAILED
        assert "didn't return a job ID" in result.error

    def test_execute_timeout(self, sample_workflow):
        # Empty WS message queue → every recv raises TimeoutError → deadline expires
        ws_patch, http_patch, _, mock_http = self._patch_stack([])
        # Stub interrupt_execution to record the call without doing real HTTP
        with ws_patch, http_patch, \
             patch("cognitive.tools.execute.interrupt_execution") as mock_interrupt:
            result = execute_workflow(
                sample_workflow,
                timeout_seconds=1,  # Force fast timeout for the test
                base_url="http://mock:8188",
            )
        assert result.status == ExecutionStatus.INTERRUPTED
        assert "did not complete within 1s" in result.error
        mock_interrupt.assert_called_once()

    def test_execute_error_event(self, sample_workflow):
        msgs = [
            json.dumps({"type": "execution_start", "data": {"prompt_id": "test_prompt"}}),
            json.dumps({
                "type": "execution_error",
                "data": {
                    "prompt_id": "test_prompt",
                    "exception_message": "OOM at node 4",
                    "node_id": "4",
                    "node_type": "KSampler",
                },
            }),
        ]
        ws_patch, http_patch, _, _ = self._patch_stack(msgs)
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.FAILED
        assert "OOM at node 4" in result.error

    def test_execute_interrupt_event(self, sample_workflow):
        msgs = [
            json.dumps({"type": "execution_start", "data": {"prompt_id": "test_prompt"}}),
            json.dumps({"type": "execution_interrupted", "data": {"prompt_id": "test_prompt"}}),
        ]
        ws_patch, http_patch, _, _ = self._patch_stack(msgs)
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.INTERRUPTED

    def test_execute_output_filenames_empty(self, sample_workflow):
        # COMPLETED with no SaveImage → empty outputs, still success
        ws_patch, http_patch, _, _ = self._patch_stack(
            _make_ws_messages(),
            history_resp=_mock_history_empty("test_prompt"),
        )
        with ws_patch, http_patch:
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.COMPLETED
        assert result.output_filenames == []
        assert result.success is True

    def test_execute_websocket_unreachable(self, sample_workflow):
        with patch("cognitive.tools.execute.websockets.sync.client.connect",
                   side_effect=OSError("connection refused")):
            result = execute_workflow(sample_workflow, base_url="http://mock:8188")
        assert result.status == ExecutionStatus.FAILED
        assert "WebSocket unreachable" in result.error


# ---------------------------------------------------------------------------
# compose_workflow
# ---------------------------------------------------------------------------

class TestComposeWorkflow:

    def test_empty_intent(self):
        result = compose_workflow("")
        assert result.success is False

    def test_basic_composition(self):
        result = compose_workflow("a beautiful sunset")
        assert result.success is True
        assert result.plan is not None
        assert result.plan.model_family == "SD1.5"

    def test_flux_detection(self):
        result = compose_workflow("flux style portrait")
        assert result.plan.model_family == "Flux"

    def test_sdxl_detection(self):
        result = compose_workflow("SDXL quality landscape")
        assert result.plan.model_family == "SDXL"

    def test_photorealistic_params(self):
        result = compose_workflow("photorealistic portrait")
        assert result.plan.parameters.get("cfg") == 7.5
        assert result.plan.parameters.get("steps") == 30

    def test_dreamy_params(self):
        result = compose_workflow("dreamy ethereal scene")
        assert result.plan.parameters.get("cfg") == 5.0

    def test_experience_patterns_applied(self):
        patterns = [{"confidence": 0.9, "parameters": {"steps": 40}}]
        result = compose_workflow("test", experience_patterns=patterns)
        assert result.plan.parameters["steps"] == 40
        assert result.plan.confidence == 0.9

    def test_explicit_model_family(self):
        result = compose_workflow("test", model_family="SD3")
        assert result.plan.model_family == "SD3"


# ---------------------------------------------------------------------------
# generate_series
# ---------------------------------------------------------------------------

class TestGenerateSeries:

    def test_empty_workflow(self):
        result = generate_series(SeriesConfig())
        assert result.success is False

    def test_no_variation(self):
        result = generate_series(SeriesConfig(base_workflow={"1": {"class_type": "N", "inputs": {}}}))
        assert result.success is False

    def test_basic_series(self):
        config = SeriesConfig(
            base_workflow={"1": {"class_type": "KSampler", "inputs": {"seed": 42}}},
            vary_params={"1.seed": [1, 2, 3, 4]},
            count=4,
        )
        result = generate_series(config)
        assert result.success is True
        assert result.planned_count == 4
        assert len(result.variations) == 4

    def test_locked_params(self):
        config = SeriesConfig(
            base_workflow={"1": {"class_type": "KSampler", "inputs": {}}},
            vary_params={"1.seed": [1, 2]},
            lock_params={"1.cfg": 7.0},
            count=2,
        )
        result = generate_series(config)
        for v in result.variations:
            assert v["mutations"]["1"]["cfg"] == 7.0


# ---------------------------------------------------------------------------
# autoresearch
# ---------------------------------------------------------------------------

class TestAutoresearch:

    def test_no_evaluator(self, engine):
        config = AutoresearchConfig(max_steps=5)
        result = autoresearch(engine, config, initial_quality=0.5)
        assert result.stopped_reason == "no_evaluator"
        assert result.steps_taken == 1

    def test_quality_threshold(self, engine):
        config = AutoresearchConfig(max_steps=10, quality_threshold=0.5)
        result = autoresearch(engine, config, initial_quality=0.8)
        assert result.stopped_reason == "quality_threshold_reached"
        assert result.steps_taken == 0

    def test_max_steps(self, engine):
        config = AutoresearchConfig(
            max_steps=3,
            quality_evaluator=lambda: 0.5,
        )
        result = autoresearch(engine, config, initial_quality=0.3)
        assert result.stopped_reason == "max_steps_reached"
        assert result.steps_taken == 3


# ---------------------------------------------------------------------------
# Cycle 32: compose_workflow no-match template fallback
# ---------------------------------------------------------------------------

class TestComposeWorkflowTemplateGuard:
    """When available_templates is provided but none match, fallback to first template."""

    def test_no_matching_template_uses_fallback(self):
        """Available templates exist but none match — must use first as fallback, not return empty data."""
        result = compose_workflow(
            "a landscape",  # → SD1.5
            available_templates=[
                {"name": "flux_base", "family": "Flux", "data": {"1": {"class_type": "CLIPTextEncode"}}},
                {"name": "sdxl_base", "family": "SDXL", "data": {"2": {}}},
            ],
        )
        # Must succeed (not fail) and use fallback — workflow_data is non-empty
        assert result.success is True
        assert result.workflow_data != {}
        assert result.plan.base_template == "flux_base"  # First template used as fallback
        assert "Warning" in result.plan.reasoning or "fallback" in result.plan.reasoning.lower()

    def test_matching_template_still_succeeds(self):
        """When a template matches the model family, success must remain True."""
        result = compose_workflow(
            "flux style image",
            available_templates=[
                {"name": "flux_base", "family": "Flux", "data": {"1": {"class_type": "CheckpointLoaderSimple"}}},
            ],
        )
        assert result.success is True
        assert result.plan.base_template == "flux_base"

    def test_empty_templates_list_does_not_trigger_fallback(self):
        """Empty list = no templates provided = compose proceeds with empty workflow_data."""
        result = compose_workflow(
            "a sunny day",
            available_templates=[],
        )
        # available_templates is falsy — the template selection block is skipped
        assert result.success is True

    def test_none_templates_does_not_trigger_failure(self):
        """None templates = compose proceeds normally."""
        result = compose_workflow("a cloudy night", available_templates=None)
        assert result.success is True
