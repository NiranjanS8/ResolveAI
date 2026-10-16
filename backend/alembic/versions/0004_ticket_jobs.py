"""Add the ticket_jobs processing queue

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ticket_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'ticket_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tickets.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('kind', sa.String(50), nullable=False, server_default='process'),
        sa.Column(
            'status',
            sa.Enum('pending', 'running', 'done', 'failed', name='job_status', native_enum=False),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claimed_by', sa.String(100), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ticket_jobs_ticket_id', 'ticket_jobs', ['ticket_id'])
    op.create_index('ix_ticket_jobs_claimable', 'ticket_jobs', ['status', 'available_at'])


def downgrade() -> None:
    op.drop_index('ix_ticket_jobs_claimable', table_name='ticket_jobs')
    op.drop_index('ix_ticket_jobs_ticket_id', table_name='ticket_jobs')
    op.drop_table('ticket_jobs')
