"""change embedding dimension from 384 to 768 (nomic-embed-text via Ollama)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = "knowledge"


def upgrade() -> None:
    # HNSW index must be dropped before altering the vector dimension
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.ix_knowledge_chunks_embedding_hnsw")
    op.execute(
        f"ALTER TABLE {SCHEMA}.knowledge_chunks ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)"
    )

    op.execute(
        f"""
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON {SCHEMA}.knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.ix_knowledge_chunks_embedding_hnsw")
    op.execute(
        f"ALTER TABLE {SCHEMA}.knowledge_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL::vector(384)"
    )

    op.execute(
        f"""
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON {SCHEMA}.knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
