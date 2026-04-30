"""Integration tests for the SQLAlchemy repository adapters (live Postgres + pgvector)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from knowledge_injector.domain.models import (
    DocumentStatus,
    IngestionRun,
    IngestionStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    SourceType,
)
from knowledge_injector.infrastructure.db.database import Database
from knowledge_injector.infrastructure.db.repositories import (
    IngestionRunRepository,
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
    KnowledgeSourceRepository,
)


def _make_source(prefix: str, cleanup: list[str]) -> KnowledgeSource:
    name = f"{prefix}-{uuid.uuid4().hex[:8]}"
    cleanup.append(name)
    return KnowledgeSource(
        name=name,
        source_type=SourceType.GIT,
        repo_url="file:///tmp/test",
        branch="main",
        base_path="",
    )


@pytest.fixture
def source_repo() -> KnowledgeSourceRepository:
    return KnowledgeSourceRepository()


@pytest.fixture
def run_repo() -> IngestionRunRepository:
    return IngestionRunRepository()


@pytest.fixture
def doc_repo() -> KnowledgeDocumentRepository:
    return KnowledgeDocumentRepository()


@pytest.fixture
def chunk_repo() -> KnowledgeChunkRepository:
    return KnowledgeChunkRepository()


class TestKnowledgeSourceRepository:
    def test_upsert_inserts_then_finds(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("src-insert", cleanup_source_names)

        with db.session() as s:
            saved = source_repo.upsert(source, s)
            assert saved.id is not None
            assert saved.name == source.name
            assert saved.created_at is not None

            found = source_repo.find_by_name(saved.name, s)
            assert found is not None
            assert found.id == saved.id

    def test_upsert_is_idempotent_on_name(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("src-idem", cleanup_source_names)

        with db.session() as s:
            first = source_repo.upsert(source, s)

        with db.session() as s:
            second = source_repo.upsert(source, s)

        assert second.id == first.id

    def test_upsert_updates_mutable_fields_on_conflict(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("src-update", cleanup_source_names)

        with db.session() as s:
            source_repo.upsert(source, s)

        source.branch = "develop"
        source.base_path = "docs"
        with db.session() as s:
            updated = source_repo.upsert(source, s)
            assert updated.branch == "develop"
            assert updated.base_path == "docs"

    def test_find_by_name_returns_none_when_missing(
        self, db: Database, source_repo: KnowledgeSourceRepository
    ):
        with db.session() as s:
            assert source_repo.find_by_name("does-not-exist-xyz", s) is None


class TestIngestionRunRepository:
    def test_create_then_find_by_id(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        run_repo: IngestionRunRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("run-create", cleanup_source_names)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        run = IngestionRun(
            source_id=source.id,
            status=IngestionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        with db.session() as s:
            created = run_repo.create(run, s)

        assert created.id is not None
        assert created.created_at is not None

        with db.session() as s:
            found = run_repo.find_by_id(created.id, s)

        assert found is not None
        assert found.status is IngestionStatus.RUNNING

    def test_update_persists_status_and_counters(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        run_repo: IngestionRunRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("run-update", cleanup_source_names)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        run = IngestionRun(
            source_id=source.id,
            status=IngestionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        with db.session() as s:
            created = run_repo.create(run, s)

        with db.session() as s:
            loaded = run_repo.find_by_id(created.id, s)
            assert loaded is not None
            loaded.status = IngestionStatus.SUCCEEDED
            loaded.files_seen = 42
            loaded.chunks_created = 7
            updated = run_repo.update(loaded, s)

        assert updated.status is IngestionStatus.SUCCEEDED
        assert updated.files_seen == 42
        assert updated.chunks_created == 7

    def test_find_by_id_returns_none_when_missing(
        self, db: Database, run_repo: IngestionRunRepository
    ):
        with db.session() as s:
            assert run_repo.find_by_id(uuid.uuid4(), s) is None

    def test_update_raises_when_run_not_found(
        self, db: Database, run_repo: IngestionRunRepository
    ):
        run = IngestionRun(
            source_id=uuid.uuid4(),
            status=IngestionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        with db.session() as s:
            with pytest.raises(ValueError):
                run_repo.update(run, s)


class TestKnowledgeDocumentRepository:
    def test_upsert_find_and_active_listing(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("doc-active", cleanup_source_names)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        doc = KnowledgeDocument(
            source_id=source.id,
            path="docs/test.md",
            content_hash="abc123",
            status=DocumentStatus.ACTIVE,
        )
        with db.session() as s:
            saved = doc_repo.upsert(doc, s)
            assert saved.id is not None

            found = doc_repo.find_by_source_and_path(source.id, "docs/test.md", s)
            assert found is not None
            assert found.content_hash == "abc123"

            active = doc_repo.find_active_by_source(source.id, s)
            assert any(d.id == saved.id for d in active)

    def test_upsert_updates_content_hash_on_conflict(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("doc-update", cleanup_source_names)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        doc = KnowledgeDocument(
            source_id=source.id,
            path="docs/update.md",
            content_hash="hash-v1",
            status=DocumentStatus.ACTIVE,
        )
        with db.session() as s:
            first = doc_repo.upsert(doc, s)

        doc.content_hash = "hash-v2"
        with db.session() as s:
            second = doc_repo.upsert(doc, s)
            again = doc_repo.find_by_source_and_path(source.id, "docs/update.md", s)

        assert second.id == first.id
        assert again is not None
        assert again.content_hash == "hash-v2"

    def test_mark_deleted_removes_from_active_listing(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        cleanup_source_names: list[str],
    ):
        source = _make_source("doc-delete", cleanup_source_names)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        doc = KnowledgeDocument(
            source_id=source.id,
            path="docs/delete.md",
            content_hash="bbb",
            status=DocumentStatus.ACTIVE,
        )
        with db.session() as s:
            saved = doc_repo.upsert(doc, s)

        with db.session() as s:
            doc_repo.mark_deleted(saved.id, s)

        with db.session() as s:
            active = doc_repo.find_active_by_source(source.id, s)
            assert not any(d.id == saved.id for d in active)
            stored = doc_repo.find_by_source_and_path(source.id, "docs/delete.md", s)
            assert stored is not None
            assert stored.status is DocumentStatus.DELETED

    def test_mark_deleted_is_noop_for_unknown_id(
        self, db: Database, doc_repo: KnowledgeDocumentRepository
    ):
        with db.session() as s:
            doc_repo.mark_deleted(uuid.uuid4(), s)

    def test_find_by_source_and_path_returns_none_when_missing(
        self, db: Database, doc_repo: KnowledgeDocumentRepository
    ):
        with db.session() as s:
            assert (
                doc_repo.find_by_source_and_path(uuid.uuid4(), "no/such.md", s) is None
            )


class TestKnowledgeChunkRepository:
    def _seed_document(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        cleanup: list[str],
        path: str,
    ) -> KnowledgeDocument:
        source = _make_source("chunk", cleanup)
        with db.session() as s:
            source = source_repo.upsert(source, s)

        doc = KnowledgeDocument(
            source_id=source.id,
            path=path,
            content_hash="seed",
            status=DocumentStatus.ACTIVE,
        )
        with db.session() as s:
            doc = doc_repo.upsert(doc, s)
        return doc

    def test_replace_inserts_chunks_with_embedding(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        chunk_repo: KnowledgeChunkRepository,
        cleanup_source_names: list[str],
    ):
        doc = self._seed_document(
            db, source_repo, doc_repo, cleanup_source_names, "docs/chunks.md"
        )
        embedding = [0.1] * 384
        chunks = [
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=i,
                content=f"chunk content {i}",
                content_hash=f"hash{i}",
                embedding=embedding,
                metadata={"position": i},
            )
            for i in range(3)
        ]

        with db.session() as s:
            result = chunk_repo.replace_for_document(doc.id, chunks, s)
            assert len(result) == 3

        with db.session() as s:
            count = s.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge.knowledge_chunks "
                    "WHERE document_id = :doc_id AND embedding IS NOT NULL"
                ),
                {"doc_id": str(doc.id)},
            ).scalar_one()
        assert count == 3

    def test_replace_is_idempotent(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        chunk_repo: KnowledgeChunkRepository,
        cleanup_source_names: list[str],
    ):
        doc = self._seed_document(
            db, source_repo, doc_repo, cleanup_source_names, "docs/idem.md"
        )
        embedding = [0.2] * 384
        chunks = [
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=i,
                content=f"c{i}",
                content_hash=f"h{i}",
                embedding=embedding,
            )
            for i in range(2)
        ]

        with db.session() as s:
            chunk_repo.replace_for_document(doc.id, chunks, s)
        with db.session() as s:
            chunk_repo.replace_for_document(doc.id, chunks, s)

        with db.session() as s:
            count = s.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge.knowledge_chunks "
                    "WHERE document_id = :doc_id"
                ),
                {"doc_id": str(doc.id)},
            ).scalar_one()
        assert count == 2

    def test_replace_handles_null_embedding(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        chunk_repo: KnowledgeChunkRepository,
        cleanup_source_names: list[str],
    ):
        doc = self._seed_document(
            db, source_repo, doc_repo, cleanup_source_names, "docs/null-emb.md"
        )
        chunks = [
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=0,
                content="no embedding",
                content_hash="x",
                embedding=None,
            )
        ]

        with db.session() as s:
            chunk_repo.replace_for_document(doc.id, chunks, s)

        with db.session() as s:
            row = s.execute(
                text(
                    "SELECT embedding IS NULL AS is_null "
                    "FROM knowledge.knowledge_chunks WHERE document_id = :doc_id"
                ),
                {"doc_id": str(doc.id)},
            ).scalar_one()
        assert row is True

    def test_delete_returns_rowcount(
        self,
        db: Database,
        source_repo: KnowledgeSourceRepository,
        doc_repo: KnowledgeDocumentRepository,
        chunk_repo: KnowledgeChunkRepository,
        cleanup_source_names: list[str],
    ):
        doc = self._seed_document(
            db, source_repo, doc_repo, cleanup_source_names, "docs/delete.md"
        )
        embedding = [0.3] * 384
        chunks = [
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=i,
                content=f"c{i}",
                content_hash=f"h{i}",
                embedding=embedding,
            )
            for i in range(3)
        ]
        with db.session() as s:
            chunk_repo.replace_for_document(doc.id, chunks, s)

        with db.session() as s:
            deleted = chunk_repo.delete_for_document(doc.id, s)
        assert deleted == 3

        with db.session() as s:
            again = chunk_repo.delete_for_document(doc.id, s)
        assert again == 0
