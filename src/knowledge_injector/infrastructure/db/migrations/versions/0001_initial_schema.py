"""initial schema — knowledge_sources, ingestion_runs, knowledge_documents, knowledge_chunks

Revision ID: 0001
Revises:
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "knowledge"


def upgrade() -> None:
    # Ensure schema and extension exist (idempotent)
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── knowledge_sources ────────────────────────────────────────────────────
    op.create_table(
        "knowledge_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("repo_url", sa.Text, nullable=False),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("base_path", sa.String(1024), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_knowledge_sources_name"),
        schema=SCHEMA,
    )

    # ── ingestion_runs ───────────────────────────────────────────────────────
    op.create_table(
        "ingestion_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repo_commit_sha", sa.String(40), nullable=True),
        sa.Column("files_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_changed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_deleted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunks_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunks_deleted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_ingestion_runs_source_id", "ingestion_runs", ["source_id"], schema=SCHEMA)
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"], schema=SCHEMA)

    # ── knowledge_documents ──────────────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column("title", sa.String(1024), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=False, server_default="text/plain"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_knowledge_documents_source_id", "knowledge_documents", ["source_id"], schema=SCHEMA)
    op.create_index("ix_knowledge_documents_source_path", "knowledge_documents", ["source_id", "path"], unique=True, schema=SCHEMA)
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"], schema=SCHEMA)

    # ── knowledge_chunks ─────────────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder — replaced below with vector(384)
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema=SCHEMA,
    )

    # Replace the placeholder text column with a proper vector(384)
    op.execute(f'ALTER TABLE {SCHEMA}.knowledge_chunks DROP COLUMN embedding')
    op.execute(f'ALTER TABLE {SCHEMA}.knowledge_chunks ADD COLUMN embedding vector(384) NULL')

    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"], schema=SCHEMA)
    op.create_index("ix_knowledge_chunks_content_hash", "knowledge_chunks", ["content_hash"], schema=SCHEMA)

    # HNSW index for fast approximate nearest-neighbour search on embeddings
    op.execute(
        f"""
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON {SCHEMA}.knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks", schema=SCHEMA)
    op.drop_table("knowledge_documents", schema=SCHEMA)
    op.drop_table("ingestion_runs", schema=SCHEMA)
    op.drop_table("knowledge_sources", schema=SCHEMA)
