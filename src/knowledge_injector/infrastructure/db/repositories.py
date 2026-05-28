"""SQLAlchemy adapters for the persistence ports."""

import json
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from knowledge_injector.domain.models import (
    DocumentStatus,
    IngestionRun,
    IngestionStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    SourceType,
)
from knowledge_injector.domain.ports import (
    IngestionRunRepositoryPort,
    KnowledgeChunkRepositoryPort,
    KnowledgeDocumentRepositoryPort,
    KnowledgeSourceRepositoryPort,
)
from knowledge_injector.infrastructure.db.orm import (
    IngestionRunORM,
    KnowledgeDocumentORM,
    KnowledgeSourceORM,
)
from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def _source_to_domain(orm: KnowledgeSourceORM) -> KnowledgeSource:
    return KnowledgeSource(
        id=orm.id,
        name=orm.name,
        source_type=SourceType(orm.source_type),
        repo_url=orm.repo_url,
        branch=orm.branch,
        base_path=orm.base_path,
        enabled=orm.enabled,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _run_to_domain(orm: IngestionRunORM) -> IngestionRun:
    return IngestionRun(
        id=orm.id,
        source_id=orm.source_id,
        status=IngestionStatus(orm.status),
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        repo_commit_sha=orm.repo_commit_sha,
        files_seen=orm.files_seen,
        files_changed=orm.files_changed,
        files_deleted=orm.files_deleted,
        chunks_created=orm.chunks_created,
        chunks_updated=orm.chunks_updated,
        chunks_deleted=orm.chunks_deleted,
        error_message=orm.error_message,
        next_run_at=orm.next_run_at,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _document_to_domain(orm: KnowledgeDocumentORM) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=orm.id,
        source_id=orm.source_id,
        path=orm.path,
        content_hash=orm.content_hash,
        status=DocumentStatus(orm.status),
        last_commit_sha=orm.last_commit_sha,
        title=orm.title,
        mime_type=orm.mime_type,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _format_embedding(embedding: list[float] | None) -> str | None:
    if embedding is None:
        return None
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"


class KnowledgeSourceRepository(KnowledgeSourceRepositoryPort):
    def upsert(self, source: KnowledgeSource, session: Session) -> KnowledgeSource:
        stmt = (
            pg_insert(KnowledgeSourceORM)
            .values(
                id=source.id,
                name=source.name,
                source_type=source.source_type.value,
                repo_url=source.repo_url,
                branch=source.branch,
                base_path=source.base_path,
                enabled=source.enabled,
            )
            .on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "source_type": source.source_type.value,
                    "repo_url": source.repo_url,
                    "branch": source.branch,
                    "base_path": source.base_path,
                    "enabled": source.enabled,
                },
            )
            .returning(KnowledgeSourceORM)
        )
        orm = session.execute(stmt).scalar_one()
        session.flush()
        return _source_to_domain(orm)

    def find_by_name(self, name: str, session: Session) -> KnowledgeSource | None:
        stmt = select(KnowledgeSourceORM).where(KnowledgeSourceORM.name == name)
        orm = session.execute(stmt).scalar_one_or_none()
        return _source_to_domain(orm) if orm is not None else None


class IngestionRunRepository(IngestionRunRepositoryPort):
    def create(self, run: IngestionRun, session: Session) -> IngestionRun:
        orm = IngestionRunORM(
            id=run.id,
            source_id=run.source_id,
            status=run.status.value,
            started_at=run.started_at,
            finished_at=run.finished_at,
            repo_commit_sha=run.repo_commit_sha,
            files_seen=run.files_seen,
            files_changed=run.files_changed,
            files_deleted=run.files_deleted,
            chunks_created=run.chunks_created,
            chunks_updated=run.chunks_updated,
            chunks_deleted=run.chunks_deleted,
            error_message=run.error_message,
            next_run_at=run.next_run_at,
        )
        session.add(orm)
        session.flush()
        session.refresh(orm)
        return _run_to_domain(orm)

    def update(self, run: IngestionRun, session: Session) -> IngestionRun:
        orm = session.get(IngestionRunORM, run.id)
        if orm is None:
            raise ValueError(f"IngestionRun not found: {run.id}")
        orm.status = run.status.value
        orm.started_at = run.started_at
        orm.finished_at = run.finished_at
        orm.repo_commit_sha = run.repo_commit_sha
        orm.files_seen = run.files_seen
        orm.files_changed = run.files_changed
        orm.files_deleted = run.files_deleted
        orm.chunks_created = run.chunks_created
        orm.chunks_updated = run.chunks_updated
        orm.chunks_deleted = run.chunks_deleted
        orm.error_message = run.error_message
        orm.next_run_at = run.next_run_at
        session.flush()
        session.refresh(orm)
        return _run_to_domain(orm)

    def find_by_id(self, run_id: UUID, session: Session) -> IngestionRun | None:
        orm = session.get(IngestionRunORM, run_id)
        return _run_to_domain(orm) if orm is not None else None


class KnowledgeDocumentRepository(KnowledgeDocumentRepositoryPort):
    def upsert(
        self, document: KnowledgeDocument, session: Session
    ) -> KnowledgeDocument:
        stmt = (
            pg_insert(KnowledgeDocumentORM)
            .values(
                id=document.id,
                source_id=document.source_id,
                path=document.path,
                content_hash=document.content_hash,
                last_commit_sha=document.last_commit_sha,
                title=document.title,
                mime_type=document.mime_type,
                status=document.status.value,
            )
            .on_conflict_do_update(
                index_elements=["source_id", "path"],
                set_={
                    "content_hash": document.content_hash,
                    "last_commit_sha": document.last_commit_sha,
                    "title": document.title,
                    "mime_type": document.mime_type,
                    "status": document.status.value,
                },
            )
            .returning(KnowledgeDocumentORM)
        )
        orm = session.execute(stmt).scalar_one()
        session.flush()
        return _document_to_domain(orm)

    def find_by_source_and_path(
        self, source_id: UUID, path: str, session: Session
    ) -> KnowledgeDocument | None:
        stmt = select(KnowledgeDocumentORM).where(
            KnowledgeDocumentORM.source_id == source_id,
            KnowledgeDocumentORM.path == path,
        )
        orm = session.execute(stmt).scalar_one_or_none()
        return _document_to_domain(orm) if orm is not None else None

    def find_active_by_source(
        self, source_id: UUID, session: Session
    ) -> list[KnowledgeDocument]:
        stmt = select(KnowledgeDocumentORM).where(
            KnowledgeDocumentORM.source_id == source_id,
            KnowledgeDocumentORM.status == DocumentStatus.ACTIVE.value,
        )
        return [_document_to_domain(orm) for orm in session.execute(stmt).scalars()]

    def mark_deleted(self, document_id: UUID, session: Session) -> None:
        orm = session.get(KnowledgeDocumentORM, document_id)
        if orm is None:
            return
        orm.status = DocumentStatus.DELETED.value
        session.flush()


class KnowledgeChunkRepository(KnowledgeChunkRepositoryPort):
    _INSERT_SQL = text(
        """
        INSERT INTO knowledge.knowledge_chunks
            (id, document_id, chunk_index, content, content_hash,
             token_count, metadata, embedding)
        VALUES
            (:id, :document_id, :chunk_index, :content, :content_hash,
             :token_count, CAST(:metadata AS jsonb),
             CAST(:embedding AS vector))
        """
    )

    _DELETE_SQL = text(
        "DELETE FROM knowledge.knowledge_chunks WHERE document_id = :document_id"
    )

    def replace_for_document(
        self,
        document_id: UUID,
        chunks: list[KnowledgeChunk],
        session: Session,
    ) -> list[KnowledgeChunk]:
        self.delete_for_document(document_id, session)
        for chunk in chunks:
            session.execute(
                self._INSERT_SQL,
                {
                    "id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "token_count": chunk.token_count,
                    "metadata": json.dumps(chunk.metadata),
                    "embedding": _format_embedding(chunk.embedding),
                },
            )
        session.flush()
        return chunks

    def delete_for_document(self, document_id: UUID, session: Session) -> int:
        result = session.execute(self._DELETE_SQL, {"document_id": str(document_id)})
        session.flush()
        return result.rowcount or 0
