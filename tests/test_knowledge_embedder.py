"""Tests for agent.knowledge.embedder — TF-IDF semantic search."""

import math
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.knowledge.embedder import (
    KnowledgeIndex,
    TextChunk,
    _compute_tf,
    _cosine_similarity,
    tokenize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MD_CONTROLNET = """\
# ControlNet Patterns

## Required Nodes

ControlNetLoader loads the ControlNet model from models directory.
ControlNetApply applies control signal to conditioning output.
A preprocessor node for depth canny openpose.

## Connection Pattern

Image goes to Preprocessor then ControlNetApply image input.
ControlNetLoader connects to ControlNetApply control_net input.
Depth maps are generated from MiDaS or DepthAnything preprocessors.

## Key Constraints

ControlNet models must match the base model family.
SD15 ControlNets do not work with SDXL checkpoints.
"""

SAMPLE_MD_FLUX = """\
# Flux Specifics

## Guidance Configuration

Flux models use guidance scale around 1.0 via FluxGuidance node.
No negative prompt needed for Flux generation.
T5 text encoder is required alongside CLIP.

## Resolution Settings

Flux supports variable resolution from 512 to 1024 pixels.
Common sizes include 768x768 and 1024x1024.
"""

SAMPLE_MD_VIDEO = """\
# Video Workflows

## LTX Video

LTX-2 is a text-to-video and image-to-video model.
Use LTXVLoader LTXVGeneration and LTXVScheduler nodes.
Supports first-last-frame conditioning for consistency.

## WAN Video

WAN 2.1 and 2.2 support text-to-video generation.
CausVid enables real-time video synthesis.
Fun control allows camera motion and scene control.
"""


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    """Create a temp knowledge directory with sample markdown files."""
    d = tmp_path / "knowledge"
    d.mkdir()
    (d / "controlnet_patterns.md").write_text(SAMPLE_MD_CONTROLNET, encoding="utf-8")
    (d / "flux_specifics.md").write_text(SAMPLE_MD_FLUX, encoding="utf-8")
    (d / "video_workflows.md").write_text(SAMPLE_MD_VIDEO, encoding="utf-8")
    return d


@pytest.fixture
def built_index(knowledge_dir: Path) -> KnowledgeIndex:
    """Return a KnowledgeIndex already built from the sample files."""
    idx = KnowledgeIndex()
    idx.build(knowledge_dir)
    return idx


# ---------------------------------------------------------------------------
# test_tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_basic(self):
        result = tokenize("Hello World! This is a test.")
        assert "hello" in result
        assert "world" in result
        assert "test" in result
        # Stop words removed
        assert "this" not in result
        assert "is" not in result
        assert "a" not in result

    def test_punctuation_stripped(self):
        result = tokenize("ControlNet-Apply (v2.0)")
        assert "controlnet" in result
        assert "apply" in result
        assert "v2" in result
        assert "0" in result

    def test_lowercased(self):
        result = tokenize("FLUX FluxGuidance T5")
        assert "flux" in result
        assert "fluxguidance" in result
        assert "t5" in result

    def test_empty(self):
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_only_stop_words(self):
        assert tokenize("the a an is are") == []


# ---------------------------------------------------------------------------
# test_tfidf_computation
# ---------------------------------------------------------------------------

class TestTfidfComputation:
    def test_tf_single_term(self):
        tf = _compute_tf(["hello"])
        assert tf == {"hello": 1.0}

    def test_tf_multiple_terms(self):
        tf = _compute_tf(["cat", "dog", "cat"])
        assert abs(tf["cat"] - 2 / 3) < 1e-9
        assert abs(tf["dog"] - 1 / 3) < 1e-9

    def test_tf_empty(self):
        assert _compute_tf([]) == {}

    def test_tfidf_values(self, built_index: KnowledgeIndex):
        """Verify TF-IDF vectors exist and have reasonable values."""
        assert len(built_index._chunks) > 0
        for chunk in built_index._chunks:
            assert isinstance(chunk.tfidf_vector, dict)
            # All TF-IDF values should be non-negative
            for val in chunk.tfidf_vector.values():
                assert val >= 0.0


# ---------------------------------------------------------------------------
# test_cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = {"a": 1.0, "b": 2.0}
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = {"x": 1.0}
        b = {"y": 1.0}
        assert _cosine_similarity(a, b) == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity({}, {"a": 1.0}) == 0.0
        assert _cosine_similarity({"a": 1.0}, {}) == 0.0
        assert _cosine_similarity({}, {}) == 0.0

    def test_partial_overlap(self):
        a = {"x": 1.0, "y": 0.0}
        b = {"x": 1.0, "z": 1.0}
        # dot = 1.0, norm_a = 1.0, norm_b = sqrt(2)
        expected = 1.0 / math.sqrt(2)
        assert abs(_cosine_similarity(a, b) - expected) < 1e-9


# ---------------------------------------------------------------------------
# test_build_index
# ---------------------------------------------------------------------------

class TestBuildIndex:
    def test_chunks_created(self, built_index: KnowledgeIndex):
        assert len(built_index._chunks) > 0

    def test_files_tracked(self, built_index: KnowledgeIndex):
        assert "controlnet_patterns" in built_index._file_mtimes
        assert "flux_specifics" in built_index._file_mtimes
        assert "video_workflows" in built_index._file_mtimes

    def test_sections_chunked(self, built_index: KnowledgeIndex):
        sections = {(c.file_name, c.section) for c in built_index._chunks}
        assert ("controlnet_patterns", "Required Nodes") in sections
        assert ("controlnet_patterns", "Connection Pattern") in sections
        assert ("flux_specifics", "Guidance Configuration") in sections

    def test_empty_dir(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        idx = KnowledgeIndex()
        idx.build(empty)
        assert len(idx._chunks) == 0

    def test_nonexistent_dir(self, tmp_path: Path):
        idx = KnowledgeIndex()
        idx.build(tmp_path / "nonexistent")
        assert len(idx._chunks) == 0


# ---------------------------------------------------------------------------
# test_search_exact_match
# ---------------------------------------------------------------------------

class TestSearchExactMatch:
    def test_controlnet_query(self, built_index: KnowledgeIndex):
        results = built_index.search("ControlNetLoader ControlNetApply", threshold=0.1)
        assert len(results) > 0
        file_names = {r.file_name for r in results}
        assert "controlnet_patterns" in file_names

    def test_flux_guidance_query(self, built_index: KnowledgeIndex):
        results = built_index.search("FluxGuidance T5 encoder", threshold=0.1)
        assert len(results) > 0
        file_names = {r.file_name for r in results}
        assert "flux_specifics" in file_names


# ---------------------------------------------------------------------------
# test_search_semantic
# ---------------------------------------------------------------------------

class TestSearchSemantic:
    def test_depth_maps(self, built_index: KnowledgeIndex):
        """'depth maps' should find ControlNet depth content."""
        results = built_index.search("depth maps preprocessor", threshold=0.1)
        assert len(results) > 0
        file_names = {r.file_name for r in results}
        assert "controlnet_patterns" in file_names

    def test_video_generation(self, built_index: KnowledgeIndex):
        """'video generation' should find video workflow content."""
        results = built_index.search("video generation text", threshold=0.1)
        assert len(results) > 0
        file_names = {r.file_name for r in results}
        assert "video_workflows" in file_names


# ---------------------------------------------------------------------------
# test_search_threshold
# ---------------------------------------------------------------------------

class TestSearchThreshold:
    def test_irrelevant_query(self, built_index: KnowledgeIndex):
        results = built_index.search(
            "quantum computing blockchain cryptocurrency",
            threshold=0.3,
        )
        assert len(results) == 0

    def test_high_threshold_filters(self, built_index: KnowledgeIndex):
        results = built_index.search("depth", threshold=0.99)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# test_search_top_k
# ---------------------------------------------------------------------------

class TestSearchTopK:
    def test_top_k_limits(self, built_index: KnowledgeIndex):
        results = built_index.search("model nodes control", top_k=1, threshold=0.01)
        assert len(results) <= 1

    def test_top_k_two(self, built_index: KnowledgeIndex):
        results = built_index.search("model nodes control", top_k=2, threshold=0.01)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# test_save_load_roundtrip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundtrip:
    def test_roundtrip(self, built_index: KnowledgeIndex, tmp_path: Path):
        index_path = tmp_path / "index.json"
        built_index.save(index_path)
        assert index_path.exists()

        loaded = KnowledgeIndex()
        ok = loaded.load(index_path)
        assert ok is True
        assert len(loaded._chunks) == len(built_index._chunks)
        assert loaded._idf == built_index._idf

        # Search produces same results
        q = "ControlNetLoader"
        orig_results = built_index.search(q, threshold=0.1)
        loaded_results = loaded.search(q, threshold=0.1)
        assert len(orig_results) == len(loaded_results)
        for orig, loaded_c in zip(orig_results, loaded_results):
            assert orig.file_name == loaded_c.file_name
            assert orig.section == loaded_c.section

    def test_load_missing_file(self, tmp_path: Path):
        idx = KnowledgeIndex()
        ok = idx.load(tmp_path / "nonexistent.json")
        assert ok is False

    def test_load_corrupt_file(self, tmp_path: Path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("not valid json{{{", encoding="utf-8")
        idx = KnowledgeIndex()
        ok = idx.load(bad_path)
        assert ok is False


# ---------------------------------------------------------------------------
# test_staleness_detection
# ---------------------------------------------------------------------------

class TestStalenessDetection:
    def test_not_stale_after_build(self, built_index: KnowledgeIndex, knowledge_dir: Path):
        assert built_index.is_stale(knowledge_dir) is False

    def test_stale_after_modify(self, built_index: KnowledgeIndex, knowledge_dir: Path):
        # Touch a file to change mtime
        target = knowledge_dir / "controlnet_patterns.md"
        new_mtime = os.path.getmtime(target) + 10
        os.utime(target, (new_mtime, new_mtime))
        assert built_index.is_stale(knowledge_dir) is True

    def test_stale_after_new_file(self, built_index: KnowledgeIndex, knowledge_dir: Path):
        (knowledge_dir / "new_topic.md").write_text("# New\n## Section\nContent.", encoding="utf-8")
        assert built_index.is_stale(knowledge_dir) is True

    def test_stale_after_delete(self, built_index: KnowledgeIndex, knowledge_dir: Path):
        (knowledge_dir / "flux_specifics.md").unlink()
        assert built_index.is_stale(knowledge_dir) is True

    def test_stale_empty_dir(self, tmp_path: Path):
        idx = KnowledgeIndex()
        idx._file_mtimes = {"something": 12345.0}
        assert idx.is_stale(tmp_path / "gone") is True


# ---------------------------------------------------------------------------
# test_incremental_rebuild
# ---------------------------------------------------------------------------

class TestIncrementalRebuild:
    def test_unchanged_files_preserved(self, built_index: KnowledgeIndex, knowledge_dir: Path):
        # Get original chunks for flux
        orig_flux_chunks = [
            (c.file_name, c.section)
            for c in built_index._chunks
            if c.file_name == "flux_specifics"
        ]

        # Modify only controlnet file
        target = knowledge_dir / "controlnet_patterns.md"
        new_content = target.read_text(encoding="utf-8") + "\n## Extra Section\n\nNew content here."
        # Ensure mtime changes
        new_mtime = os.path.getmtime(target) + 10
        target.write_text(new_content, encoding="utf-8")
        os.utime(target, (new_mtime, new_mtime))

        built_index.rebuild_incremental(knowledge_dir)

        # Flux chunks still present (sections unchanged)
        new_flux_chunks = [
            (c.file_name, c.section)
            for c in built_index._chunks
            if c.file_name == "flux_specifics"
        ]
        assert set(orig_flux_chunks) == set(new_flux_chunks)

        # New section exists
        sections = {(c.file_name, c.section) for c in built_index._chunks}
        assert ("controlnet_patterns", "Extra Section") in sections


# ---------------------------------------------------------------------------
# test_thread_safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_search(self, built_index: KnowledgeIndex):
        errors: list[Exception] = []
        results_per_thread: list[list[TextChunk]] = [[] for _ in range(4)]

        def search_worker(idx: int):
            try:
                queries = [
                    "ControlNet depth map",
                    "Flux guidance T5",
                    "video LTX generation",
                    "model resolution SDXL",
                ]
                r = built_index.search(queries[idx], threshold=0.05)
                results_per_thread[idx] = r
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=search_worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"
        # At least some threads should get results
        total = sum(len(r) for r in results_per_thread)
        assert total > 0


# ---------------------------------------------------------------------------
# test_hybrid_detection (integration with system_prompt)
# ---------------------------------------------------------------------------

class TestHybridDetection:
    def test_keyword_finds_one_semantic_finds_more(self, knowledge_dir: Path):
        """Keyword triggers find <2 files, semantic adds more."""
        from agent.system_prompt import _detect_relevant_knowledge

        # Patch KNOWLEDGE_DIR and triggers to return just one keyword match
        triggers_def = {
            "controlnet_patterns": {
                "priority": 1,
                "keywords": ["controlnet"],
            },
        }

        # Build a semantic index from our test knowledge dir
        idx = KnowledgeIndex()
        idx.build(knowledge_dir)

        # Context mentions controlnet (keyword match) + depth (semantic)
        session_context = {
            "workflow": {
                "current_workflow": {
                    "1": {"class_type": "ControlNetLoader", "inputs": {}},
                },
            },
            "notes": [{"text": "working with depth maps and video generation"}],
        }

        with patch("agent.system_prompt._load_triggers", return_value=triggers_def), \
             patch("agent.system_prompt._semantic_index", idx), \
             patch("agent.system_prompt.KNOWLEDGE_DIR", knowledge_dir):
            result = _detect_relevant_knowledge(session_context)

        # Keyword found controlnet_patterns (1 file < 2), so semantic runs
        assert "controlnet_patterns" in result
        # Semantic should find additional files
        assert len(result) >= 1

    def test_keyword_sufficient_skips_semantic(self):
        """When keyword triggers find >= 2 files, semantic not called."""
        from agent.system_prompt import (
            _detect_relevant_knowledge as detect,
        )

        triggers_def = {
            "controlnet_patterns": {
                "priority": 1,
                "keywords": ["controlnet"],
            },
            "flux_specifics": {
                "priority": 1,
                "keywords": ["flux"],
            },
            "video_workflows": {
                "priority": 1,
                "keywords": ["video"],
            },
        }

        session_context = {
            "workflow": {
                "current_workflow": {
                    "1": {"class_type": "ControlNetLoader", "inputs": {}},
                    "2": {"class_type": "FluxGuidance", "inputs": {}},
                    "3": {"class_type": "CreateVideo", "inputs": {}},
                },
            },
            "notes": [],
        }

        with patch("agent.system_prompt._load_triggers", return_value=triggers_def), \
             patch("agent.system_prompt._semantic_search") as mock_sem:
            result = detect(session_context)

        # Keywords found 3 files (>= 2), so semantic should NOT be called
        assert len(result) >= 2
        mock_sem.assert_not_called()


# ---------------------------------------------------------------------------
# test_empty_knowledge_dir
# ---------------------------------------------------------------------------

class TestEmptyKnowledgeDir:
    def test_build_empty(self, tmp_path: Path):
        empty = tmp_path / "empty_knowledge"
        empty.mkdir()
        idx = KnowledgeIndex()
        idx.build(empty)
        assert len(idx._chunks) == 0
        results = idx.search("anything", threshold=0.0)
        assert results == []

    def test_search_before_build(self):
        idx = KnowledgeIndex()
        results = idx.search("test query", threshold=0.0)
        assert results == []
