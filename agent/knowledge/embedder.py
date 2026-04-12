"""Pure-Python TF-IDF knowledge index with cosine similarity search.

Zero external dependencies — no sklearn, numpy, or sentence-transformers.
Chunks knowledge markdown files by ## headers and builds sparse TF-IDF vectors
for semantic retrieval.
"""

import json
import logging
import math
import os
import re
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# Small stop-word set covering function words that add noise to TF-IDF.
STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "and", "or",
    "but", "if", "then", "for", "to", "of", "in", "on", "at", "by",
    "with", "from", "this", "that", "it", "its", "not", "no",
})

_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, remove stop words."""
    tokens = _SPLIT_RE.split(text.lower())
    return [t for t in tokens if t and t not in STOP_WORDS]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total_terms."""
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors (dicts)."""
    if not a or not b:
        return 0.0
    # Dot product over shared keys
    dot = 0.0
    for term, val_a in a.items():
        val_b = b.get(term)
        if val_b is not None:
            dot += val_a * val_b
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class TextChunk:
    """A chunk of knowledge text with its TF-IDF vector."""

    __slots__ = ("file_name", "section", "text", "tfidf_vector")

    def __init__(
        self,
        file_name: str,
        section: str,
        text: str,
        tfidf_vector: dict[str, float],
    ) -> None:
        self.file_name = file_name
        self.section = section
        self.text = text
        self.tfidf_vector = tfidf_vector

    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "section": self.section,
            "text": self.text,
            "tfidf_vector": self.tfidf_vector,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TextChunk":
        return cls(
            file_name=d["file_name"],
            section=d["section"],
            text=d["text"],
            tfidf_vector=d["tfidf_vector"],
        )


def _chunk_markdown(file_name: str, content: str) -> list[dict]:
    """Split markdown by ## headers into raw chunk dicts (no TF-IDF yet).

    Returns list of {"file_name", "section", "text", "tokens"}.
    """
    chunks: list[dict] = []
    current_section = "intro"
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            # Flush previous section
            text = "\n".join(current_lines).strip()
            if text:
                tokens = tokenize(text)
                if tokens:
                    chunks.append({
                        "file_name": file_name,
                        "section": current_section,
                        "text": text,
                        "tokens": tokens,
                    })
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Flush last section
    text = "\n".join(current_lines).strip()
    if text:
        tokens = tokenize(text)
        if tokens:
            chunks.append({
                "file_name": file_name,
                "section": current_section,
                "text": text,
                "tokens": tokens,
            })

    return chunks


class KnowledgeIndex:
    """TF-IDF index over knowledge markdown files."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chunks: list[TextChunk] = []
        self._idf: dict[str, float] = {}
        self._file_mtimes: dict[str, float] = {}
        # Raw chunk data before TF-IDF (for incremental rebuild)
        self._raw_chunks: list[dict] = []

    def build(self, knowledge_dir: Path) -> None:
        """Read all .md files, chunk by ## headers, compute TF-IDF vectors."""
        with self._lock:
            self._raw_chunks = []
            self._file_mtimes = {}

            if not knowledge_dir.exists():
                self._chunks = []
                self._idf = {}
                return

            for md_file in sorted(knowledge_dir.glob("*.md")):
                try:
                    content = md_file.read_text(encoding="utf-8")
                except Exception as exc:
                    log.debug("Could not read %s: %s", md_file.name, exc)
                    continue
                stem = md_file.stem
                self._file_mtimes[stem] = os.path.getmtime(md_file)
                file_chunks = _chunk_markdown(stem, content)
                self._raw_chunks.extend(file_chunks)

            self._recompute_tfidf()

    def _recompute_tfidf(self) -> None:
        """Recompute IDF and TF-IDF vectors from raw chunks. Caller holds lock."""
        total_docs = len(self._raw_chunks)
        if total_docs == 0:
            self._chunks = []
            self._idf = {}
            return

        # Document frequency
        df: dict[str, int] = {}
        for chunk in self._raw_chunks:
            unique_terms = set(chunk["tokens"])
            for term in unique_terms:
                df[term] = df.get(term, 0) + 1

        # IDF: log(total_docs / docs_containing_term)
        self._idf = {
            term: math.log(total_docs / count)
            for term, count in df.items()
        }

        # Build TextChunk objects with TF-IDF vectors
        self._chunks = []
        for chunk in self._raw_chunks:
            tf = _compute_tf(chunk["tokens"])
            tfidf_vec = {
                term: tf_val * self._idf.get(term, 0.0)
                for term, tf_val in tf.items()
            }
            self._chunks.append(TextChunk(
                file_name=chunk["file_name"],
                section=chunk["section"],
                text=chunk["text"],
                tfidf_vector=tfidf_vec,
            ))

    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.3,
    ) -> list[TextChunk]:
        """Find chunks most similar to query via cosine similarity."""
        with self._lock:
            if not self._chunks:
                return []

            tokens = tokenize(query)
            if not tokens:
                return []

            # Build query TF-IDF vector using index IDF
            tf = _compute_tf(tokens)
            query_vec = {
                term: tf_val * self._idf.get(term, 0.0)
                for term, tf_val in tf.items()
                if term in self._idf
            }
            if not query_vec:
                return []

            scored: list[tuple[float, TextChunk]] = []
            for chunk in self._chunks:
                sim = _cosine_similarity(query_vec, chunk.tfidf_vector)
                if sim >= threshold:
                    scored.append((sim, chunk))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [chunk for _, chunk in scored[:top_k]]

    def save(self, path: Path) -> None:
        """Serialize index to JSON."""
        with self._lock:
            data = {
                "files": self._file_mtimes,
                "idf": self._idf,
                "chunks": [c.to_dict() for c in self._chunks],
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True)

    def load(self, path: Path) -> bool:
        """Deserialize index from JSON. Returns False if file missing or corrupt."""
        if not path.exists():
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.debug("Could not load index from %s: %s", path, exc)
            return False

        with self._lock:
            self._file_mtimes = data.get("files", {})
            self._idf = data.get("idf", {})
            self._chunks = [
                TextChunk.from_dict(d)
                for d in data.get("chunks", [])
            ]
            # Rebuild raw_chunks from loaded data (for incremental rebuild)
            self._raw_chunks = []
            for chunk in self._chunks:
                self._raw_chunks.append({
                    "file_name": chunk.file_name,
                    "section": chunk.section,
                    "text": chunk.text,
                    "tokens": tokenize(chunk.text),
                })
        return True

    def is_stale(self, knowledge_dir: Path) -> bool:
        """Compare stored file mtimes against current mtimes on disk."""
        if not knowledge_dir.exists():
            return bool(self._file_mtimes)

        current_files: set[str] = set()
        for md_file in knowledge_dir.glob("*.md"):
            stem = md_file.stem
            current_files.add(stem)
            stored_mtime = self._file_mtimes.get(stem)
            if stored_mtime is None:
                return True  # New file
            current_mtime = os.path.getmtime(md_file)
            if abs(current_mtime - stored_mtime) > 0.01:
                return True  # Modified file

        # Check for deleted files
        if set(self._file_mtimes.keys()) != current_files:
            return True

        return False

    def rebuild_incremental(self, knowledge_dir: Path) -> None:
        """Rebuild only changed files' chunks, recompute IDF globally."""
        with self._lock:
            if not knowledge_dir.exists():
                self._raw_chunks = []
                self._file_mtimes = {}
                self._recompute_tfidf()
                return

            current_files: dict[str, Path] = {}
            for md_file in sorted(knowledge_dir.glob("*.md")):
                current_files[md_file.stem] = md_file

            # Find changed/new/deleted files
            changed_stems: set[str] = set()
            for stem, md_path in current_files.items():
                current_mtime = os.path.getmtime(md_path)
                stored_mtime = self._file_mtimes.get(stem)
                if stored_mtime is None or abs(current_mtime - stored_mtime) > 0.01:
                    changed_stems.add(stem)

            deleted_stems = set(self._file_mtimes.keys()) - set(current_files.keys())

            # Remove chunks from changed/deleted files
            remove_stems = changed_stems | deleted_stems
            self._raw_chunks = [
                c for c in self._raw_chunks
                if c["file_name"] not in remove_stems
            ]

            # Remove mtimes for deleted files
            for stem in deleted_stems:
                self._file_mtimes.pop(stem, None)

            # Add chunks for changed/new files
            for stem in changed_stems:
                md_path = current_files[stem]
                try:
                    content = md_path.read_text(encoding="utf-8")
                except Exception as exc:
                    log.debug("Could not read %s: %s", md_path.name, exc)
                    continue
                self._file_mtimes[stem] = os.path.getmtime(md_path)
                file_chunks = _chunk_markdown(stem, content)
                self._raw_chunks.extend(file_chunks)

            self._recompute_tfidf()
