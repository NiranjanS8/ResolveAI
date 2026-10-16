"""Store knowledge_chunks embeddings in pgvector and add document metadata

Revision ID: 0003
Revises: 0002
Create Date: 2024-03-01 00:00:00.000000

The embedding column becomes an unconstrained ``vector`` rather than a fixed
``vector(N)``: the embedding provider is switchable (gemini 768, mistral 1024,
openai 1536) and a pinned dimension would force a new migration on every
provider change. Retrieval therefore uses pgvector's cosine operator with a
dimension guard instead of an ANN index.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column('knowledge_chunks', sa.Column('doc_title', sa.String(500), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('source_path', sa.Text(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('chunk_index', sa.Integer(), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('content_hash', sa.String(64), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_model', sa.String(100), nullable=True))

    # FLOAT[] -> vector, preserving the existing row embeddings.
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_vec vector")
    op.execute(
        "UPDATE knowledge_chunks "
        "SET embedding_vec = ('[' || array_to_string(embedding, ',') || ']')::vector "
        "WHERE embedding IS NOT NULL"
    )
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE knowledge_chunks RENAME COLUMN embedding_vec TO embedding")

    op.create_index(
        'ix_knowledge_chunks_source_path', 'knowledge_chunks', ['source_path']
    )
    op.create_index(
        'ix_knowledge_chunks_content_hash', 'knowledge_chunks', ['content_hash']
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_content_hash', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_source_path', table_name='knowledge_chunks')

    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_arr double precision[]")
    op.execute(
        "UPDATE knowledge_chunks "
        "SET embedding_arr = string_to_array(trim(both '[]' from embedding::text), ',')::double precision[] "
        "WHERE embedding IS NOT NULL"
    )
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE knowledge_chunks RENAME COLUMN embedding_arr TO embedding")

    op.drop_column('knowledge_chunks', 'embedding_model')
    op.drop_column('knowledge_chunks', 'content_hash')
    op.drop_column('knowledge_chunks', 'chunk_index')
    op.drop_column('knowledge_chunks', 'source_path')
    op.drop_column('knowledge_chunks', 'doc_title')
