"""Initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types with checkfirst=True
    ticket_status = postgresql.ENUM(
        'new', 'classifying', 'retrieving', 'deciding',
        'auto_resolved', 'draft_for_review', 'escalated', 'resolved',
        name='ticket_status', create_type=False
    )
    ticket_status.create(op.get_bind(), checkfirst=True)
    
    intent_enum = postgresql.ENUM(
        'general', 'billing', 'technical', 'account', 'refund',
        'order_status', 'password_reset', 'cancellation',
        name='intent', create_type=False
    )
    intent_enum.create(op.get_bind(), checkfirst=True)

    # tickets table
    op.create_table(
        'tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('status', ticket_status, nullable=False, server_default='new'),
        sa.Column('intent', intent_enum, nullable=True),
        sa.Column('urgency', sa.String(50), nullable=True),
        sa.Column('sentiment', sa.String(50), nullable=True),
        sa.Column('confidence', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_tickets_customer_id', 'tickets', ['customer_id'])
    op.create_index('ix_tickets_status', 'tickets', ['status'])
    op.create_index('ix_tickets_intent', 'tickets', ['intent'])

    # ticket_messages table
    op.create_table(
        'ticket_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('meta', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ticket_messages_ticket_id', 'ticket_messages', ['ticket_id'])

    # audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=True),
        sa.Column('confidence', sa.String(50), nullable=True),
        sa.Column('executed_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_log_ticket_id', 'audit_log', ['ticket_id'])
    op.create_index('ix_audit_log_ticket_created', 'audit_log', ['ticket_id', 'created_at'])

    # knowledge_chunks table
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_id', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column('meta', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_knowledge_chunks_source', 'knowledge_chunks', ['source_id', 'source_type'])

    # agent_feedback table
    op.create_table(
        'agent_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticket_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_draft', sa.Text, nullable=False),
        sa.Column('edited_response', sa.Text, nullable=False),
        sa.Column('agent_id', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_agent_feedback_ticket_id', 'agent_feedback', ['ticket_id'])

    # provider_calls table
    op.create_table(
        'provider_calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('task', sa.String(50), nullable=False),
        sa.Column('input_tokens', sa.String(50), nullable=True),
        sa.Column('output_tokens', sa.String(50), nullable=True),
        sa.Column('latency_ms', sa.String(50), nullable=True),
        sa.Column('cost_estimate', sa.String(50), nullable=True),
        sa.Column('success', sa.String(50), nullable=False),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_provider_calls_task_created', 'provider_calls', ['task', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_provider_calls_task_created', table_name='provider_calls')
    op.drop_table('provider_calls')
    
    op.drop_index('ix_agent_feedback_ticket_id', table_name='agent_feedback')
    op.drop_table('agent_feedback')
    
    op.drop_index('ix_knowledge_chunks_source', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    
    op.drop_index('ix_audit_log_ticket_created', table_name='audit_log')
    op.drop_index('ix_audit_log_ticket_id', table_name='audit_log')
    op.drop_table('audit_log')
    
    op.drop_index('ix_ticket_messages_ticket_id', table_name='ticket_messages')
    op.drop_table('ticket_messages')
    
    op.drop_index('ix_tickets_intent', table_name='tickets')
    op.drop_index('ix_tickets_status', table_name='tickets')
    op.drop_index('ix_tickets_customer_id', table_name='tickets')
    op.drop_table('tickets')
    
    op.execute('DROP TYPE IF EXISTS ticket_status')
    op.execute('DROP TYPE IF EXISTS intent')