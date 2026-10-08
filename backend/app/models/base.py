import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy import Float
from sqlalchemy.orm import relationship

from app.db.session import Base


class TicketStatus(str, enum.Enum):
    NEW = "new"
    CLASSIFYING = "classifying"
    RETRIEVING = "retrieving"
    DECIDING = "deciding"
    AUTO_RESOLVED = "auto_resolved"
    DRAFT_FOR_REVIEW = "draft_for_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"

    @staticmethod
    def values(_cls) -> list[str]:
        return [e.value for e in TicketStatus]


class Intent(str, enum.Enum):
    GENERAL = "general"
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    REFUND = "refund"
    ORDER_STATUS = "order_status"
    PASSWORD_RESET = "password_reset"
    CANCELLATION = "cancellation"

    @staticmethod
    def values(_cls) -> list[str]:
        return [e.value for e in Intent]


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(
        Enum(TicketStatus, name="ticket_status", values_callable=TicketStatus.values, native_enum=False),
        default=TicketStatus.NEW,
        nullable=False,
        index=True,
    )
    intent = Column(Enum(Intent, name="intent", values_callable=Intent.values, native_enum=False), nullable=True, index=True)
    urgency = Column(String(50), nullable=True)
    sentiment = Column(String(50), nullable=True)
    confidence = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="ticket", cascade="all, delete-orphan")
    feedback = relationship("AgentFeedback", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="messages")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=True)
    confidence = Column(String(50), nullable=True)
    executed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_log_ticket_created", "ticket_id", "created_at"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id = Column(String(255), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float), nullable=True)
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_knowledge_chunks_source", "source_id", "source_type"),
    )


class AgentFeedback(Base):
    __tablename__ = "agent_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    original_draft = Column(Text, nullable=False)
    edited_response = Column(Text, nullable=False)
    agent_id = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="feedback")


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    task = Column(String(50), nullable=False)
    input_tokens = Column(String(50), nullable=True)
    output_tokens = Column(String(50), nullable=True)
    latency_ms = Column(String(50), nullable=True)
    cost_estimate = Column(String(50), nullable=True)
    success = Column(String(50), nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_provider_calls_task_created", "task", "created_at"),
    )