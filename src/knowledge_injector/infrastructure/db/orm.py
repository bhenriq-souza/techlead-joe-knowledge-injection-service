"""SQLAlchemy ORM models and Base metadata."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class KnowledgeSourceORM(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = {"schema": "knowledge"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    base_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestionRunORM(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_source_id", "source_id"),
        {"schema": "knowledge"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge.knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repo_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeDocumentORM(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_source_id", "source_id"),
        Index("ix_knowledge_documents_source_path", "source_id", "path", unique=True),
        Index("ix_knowledge_documents_status", "status"),
        {"schema": "knowledge"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge.knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="text/plain")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeChunkORM(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_document_id", "document_id"),
        {"schema": "knowledge"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge.knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # embedding is handled as a raw Column in the migration (pgvector type)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
