"""Unit tests for the pure helpers in repositories.py (no DB required)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from knowledge_injector.domain.models import (
    DocumentStatus,
    IngestionStatus,
    SourceType,
)
from knowledge_injector.infrastructure.db.repositories import (
    _document_to_domain,
    _format_embedding,
    _run_to_domain,
    _source_to_domain,
)


class TestFormatEmbedding:
    def test_returns_none_when_input_is_none(self):
        assert _format_embedding(None) is None

    def test_serializes_floats_into_pgvector_literal(self):
        result = _format_embedding([0.1, 0.2, 0.3])
        assert result is not None
        assert result.startswith("[") and result.endswith("]")
        parts = result[1:-1].split(",")
        assert [float(p) for p in parts] == [0.1, 0.2, 0.3]

    def test_handles_empty_list(self):
        assert _format_embedding([]) == "[]"

    def test_coerces_int_like_values_to_float(self):
        result = _format_embedding([1, 2, 3])
        assert result is not None
        assert [float(p) for p in result[1:-1].split(",")] == [1.0, 2.0, 3.0]


class TestSourceToDomain:
    def test_maps_all_fields(self):
        now = datetime.now(timezone.utc)
        source_id = uuid4()
        orm = SimpleNamespace(
            id=source_id,
            name="repo-x",
            source_type="git",
            repo_url="https://example.test/repo.git",
            branch="main",
            base_path="docs",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        domain = _source_to_domain(orm)

        assert domain.id == source_id
        assert domain.name == "repo-x"
        assert domain.source_type is SourceType.GIT
        assert domain.repo_url == "https://example.test/repo.git"
        assert domain.branch == "main"
        assert domain.base_path == "docs"
        assert domain.enabled is True
        assert domain.created_at == now
        assert domain.updated_at == now


class TestRunToDomain:
    def test_maps_all_fields_and_converts_status(self):
        now = datetime.now(timezone.utc)
        run_id = uuid4()
        source_id = uuid4()
        orm = SimpleNamespace(
            id=run_id,
            source_id=source_id,
            status="succeeded",
            started_at=now,
            finished_at=now,
            repo_commit_sha="abc123",
            files_seen=10,
            files_changed=2,
            files_deleted=1,
            chunks_created=5,
            chunks_updated=3,
            chunks_deleted=1,
            error_message=None,
            next_run_at=None,
            created_at=now,
            updated_at=now,
        )

        domain = _run_to_domain(orm)

        assert domain.id == run_id
        assert domain.source_id == source_id
        assert domain.status is IngestionStatus.SUCCEEDED
        assert domain.repo_commit_sha == "abc123"
        assert domain.files_seen == 10
        assert domain.files_changed == 2
        assert domain.chunks_updated == 3


class TestDocumentToDomain:
    def test_maps_all_fields_and_converts_status(self):
        now = datetime.now(timezone.utc)
        doc_id = uuid4()
        source_id = uuid4()
        orm = SimpleNamespace(
            id=doc_id,
            source_id=source_id,
            path="docs/intro.md",
            content_hash="hash-1",
            status="active",
            last_commit_sha="def456",
            title="Intro",
            mime_type="text/markdown",
            created_at=now,
            updated_at=now,
        )

        domain = _document_to_domain(orm)

        assert domain.id == doc_id
        assert domain.source_id == source_id
        assert domain.path == "docs/intro.md"
        assert domain.content_hash == "hash-1"
        assert domain.status is DocumentStatus.ACTIVE
        assert domain.last_commit_sha == "def456"
        assert domain.title == "Intro"
        assert domain.mime_type == "text/markdown"
