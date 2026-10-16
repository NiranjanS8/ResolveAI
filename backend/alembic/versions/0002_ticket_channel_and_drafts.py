"""Add channel, draft_response and retrieved_context to tickets

Revision ID: 0002
Revises: 0001
Create Date: 2024-02-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tickets',
        sa.Column('channel', sa.String(20), nullable=False, server_default='chat'),
    )
    op.add_column('tickets', sa.Column('draft_response', sa.Text, nullable=True))
    op.add_column('tickets', sa.Column('retrieved_context', postgresql.JSONB, nullable=True))
    op.create_index('ix_tickets_channel', 'tickets', ['channel'])


def downgrade() -> None:
    op.drop_index('ix_tickets_channel', table_name='tickets')
    op.drop_column('tickets', 'retrieved_context')
    op.drop_column('tickets', 'draft_response')
    op.drop_column('tickets', 'channel')
