"""Streaming loader for the candidate pool.

The pool is ~100K candidate records as newline-delimited JSON (JSONL). It ships
as a single large file (~465 MB uncompressed). We never want to hold the parsed
objects in memory unless a caller explicitly asks for the full list, so the
primary entry point is the lazy `iter_candidates` generator.

The on-disk file may be either gzip-compressed (`candidates.jsonl.gz`) or plain
(`candidates.jsonl`). We detect which by reading the gzip magic bytes rather than
trusting the extension, so the same code path works regardless of how the data
was distributed.
"""

from __future__ import annotations

import gzip
import io
import json
import os
from typing import Iterator

# Resolve paths relative to the repo root (this file lives in src/).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")

# Candidate filenames in preference order. We try the compressed name first to
# match the documented layout, then fall back to the plain file.
_CANDIDATE_FILENAMES = ("candidates.jsonl.gz", "candidates.jsonl")

# gzip files begin with these two magic bytes (RFC 1952).
_GZIP_MAGIC = b"\x1f\x8b"


def default_path() -> str:
    """Return the path to the candidate pool, preferring the compressed file.

    Raises FileNotFoundError if neither candidate file is present so callers get
    an actionable error instead of a confusing parse failure later.
    """
    for name in _CANDIDATE_FILENAMES:
        candidate = os.path.join(_DATA_DIR, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        "No candidate pool found. Expected one of "
        f"{_CANDIDATE_FILENAMES} in {_DATA_DIR}. "
        "See README for how to obtain the data."
    )


def _open_text(path: str) -> io.TextIOBase:
    """Open `path` as a UTF-8 text stream, transparently handling gzip.

    Detection is by magic bytes, not extension, so a mislabeled file still works.
    """
    with open(path, "rb") as probe:
        is_gzip = probe.read(2) == _GZIP_MAGIC
    if is_gzip:
        return gzip.open(path, mode="rt", encoding="utf-8")
    return open(path, mode="rt", encoding="utf-8")


def iter_candidates(path: str | None = None) -> Iterator[dict]:
    """Yield candidate records one at a time, streaming from disk.

    Blank lines are skipped. The file handle is closed when the generator is
    exhausted or garbage-collected.
    """
    if path is None:
        path = default_path()
    with _open_text(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_all(path: str | None = None) -> list[dict]:
    """Eagerly load every candidate into a list.

    Convenience wrapper for the scoring pass and the Phase 0 checkpoint. Holds
    all 100K records in memory at once; prefer `iter_candidates` for streaming.
    """
    return list(iter_candidates(path))
