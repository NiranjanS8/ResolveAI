import React, { useState } from 'react';
import { type Ticket } from '../api/tickets';
import { DraftCard } from './DraftCard';
import { ActionButtons } from './ActionButtons';

interface TicketDetailPaneProps {
  ticket: Ticket;
  onApprove: (ticket: Ticket) => void;
  onEdit: (ticket: Ticket, editedDraft: string) => void;
  onReject: (ticket: Ticket) => void;
  onRefund: (ticket: Ticket, amount: number) => void;
  onOrderStatus: (ticket: Ticket) => void;
  onPasswordReset: (ticket: Ticket) => void;
  onSendMessage: (ticket: Ticket, text: string) => void;
  onClose?: () => void;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft_for_review: { label: 'Needs review', color: 'var(--yellow)', bg: 'var(--yellow-dim)' },
  auto_resolved:    { label: 'Auto-resolved', color: 'var(--green)',  bg: 'var(--green-dim)'  },
  escalated:        { label: 'Escalated',     color: 'var(--red)',    bg: 'var(--red-dim)'    },
  resolved:         { label: 'Resolved',      color: 'var(--green)',  bg: 'var(--green-dim)'  },
  new:              { label: 'New',           color: 'var(--accent)', bg: 'var(--accent-dim)' },
};

const URGENCY_CONFIG: Record<string, { color: string; bg: string }> = {
  critical: { color: 'var(--red)',    bg: 'var(--red-dim)'    },
  high:     { color: 'var(--yellow)', bg: 'var(--yellow-dim)' },
  medium:   { color: 'var(--text-secondary)', bg: 'var(--bg-elevated)' },
  low:      { color: 'var(--text-muted)',      bg: 'var(--bg-elevated)' },
};

const SENTIMENT_CONFIG: Record<string, { symbol: string; color: string }> = {
  negative: { symbol: '↓', color: 'var(--red)'    },
  neutral:  { symbol: '→', color: 'var(--text-secondary)' },
  positive: { symbol: '↑', color: 'var(--green)'  },
};

export const TicketDetailPane: React.FC<TicketDetailPaneProps> = ({
  ticket,
  onApprove,
  onEdit,
  onReject,
  onRefund,
  onOrderStatus,
  onPasswordReset,
  onSendMessage,
  onClose,
}) => {
  const [replyText, setReplyText] = useState('');
  const [activeTab, setActiveTab] = useState<'conversation' | 'audit'>('conversation');

  const handleSendReply = (e: React.FormEvent) => {
    e.preventDefault();
    if (replyText.trim()) {
      onSendMessage(ticket, replyText.trim());
      setReplyText('');
    }
  };

  const statusCfg   = STATUS_CONFIG[ticket.status]  || STATUS_CONFIG.new;
  const urgencyCfg  = URGENCY_CONFIG[ticket.urgency || 'low'] || URGENCY_CONFIG.low;
  const sentimentCfg = SENTIMENT_CONFIG[ticket.sentiment || 'neutral'] || SENTIMENT_CONFIG.neutral;
  const confidencePct = Math.round((ticket.confidence || 0) * 100);
  const confColor =
    confidencePct >= 90 ? 'var(--green)' :
    confidencePct >= 75 ? 'var(--yellow)' : 'var(--red)';

  return (
    <div
      className="flex flex-col h-full rounded-lg overflow-hidden animate-slide-in"
      style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
    >
      {/* ─── Header ───────────────────────────── */}
      <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--border)' }}>
        {/* Top meta row */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs font-semibold" style={{ color: 'var(--accent)' }}>
              #{ticket.id}
            </span>
            <span
              className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-sm font-semibold"
              style={{
                backgroundColor: ticket.channel === 'email' ? 'var(--green-dim)' : 'var(--accent-dim)',
                color: ticket.channel === 'email' ? 'var(--green)' : 'var(--accent)',
              }}
            >
              {ticket.channel}
            </span>
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ backgroundColor: statusCfg.bg, color: statusCfg.color }}
            >
              {statusCfg.label}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {new Date(ticket.created_at).toLocaleString([], {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
              })}
            </span>
            {onClose && (
              <button
                onClick={onClose}
                className="w-6 h-6 rounded flex items-center justify-center text-sm transition-colors"
                style={{ color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Subject */}
        <h2 className="text-base font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          {ticket.subject}
        </h2>
        <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
          {ticket.customer_id}
        </div>
      </div>

      {/* ─── AI Telemetry Strip ───────────────── */}
      <div
        className="px-5 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs"
        style={{ backgroundColor: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)' }}
      >
        {/* Intent */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: 'var(--text-muted)' }}>Intent</span>
          <span
            className="font-mono px-1.5 py-0.5 rounded font-medium"
            style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--accent)', border: '1px solid var(--border)' }}
          >
            {ticket.intent || '—'}
          </span>
        </div>

        {/* Urgency */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: 'var(--text-muted)' }}>Urgency</span>
          <span
            className="font-mono uppercase text-[10px] px-1.5 py-0.5 rounded font-semibold"
            style={{ backgroundColor: urgencyCfg.bg, color: urgencyCfg.color }}
          >
            {ticket.urgency || 'std'}
          </span>
        </div>

        {/* Sentiment */}
        <div className="flex items-center gap-1.5">
          <span style={{ color: 'var(--text-muted)' }}>Sentiment</span>
          <span className="font-medium capitalize" style={{ color: sentimentCfg.color }}>
            {sentimentCfg.symbol} {ticket.sentiment || 'neutral'}
          </span>
        </div>

        {/* Confidence — right-aligned */}
        <div className="flex items-center gap-2 ml-auto">
          <span style={{ color: 'var(--text-muted)' }}>Confidence</span>
          <div className="conf-bar-track w-20">
            <div
              className="conf-bar-fill"
              style={{ width: `${confidencePct}%`, backgroundColor: confColor }}
            />
          </div>
          <span className="font-mono font-semibold" style={{ color: confColor }}>
            {confidencePct}%
          </span>
        </div>
      </div>

      {/* ─── Tabs ─────────────────────────────── */}
      <div
        className="flex items-center px-5 gap-1"
        style={{ backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
      >
        {[
          { id: 'conversation' as const, label: `Conversation (${ticket.messages?.length || 1})` },
          { id: 'audit'        as const, label: `Audit Log (${ticket.audit_logs?.length || 0})`  },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="py-2.5 px-1 text-xs font-medium border-b-2 transition-colors"
            style={{
              borderColor: activeTab === tab.id ? 'var(--accent)'     : 'transparent',
              color:        activeTab === tab.id ? 'var(--accent)'     : 'var(--text-secondary)',
              marginRight: '12px',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ─── Content ──────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {activeTab === 'conversation' ? (
          <>
            {/* Messages */}
            <div className="space-y-3">
              {ticket.messages && ticket.messages.length > 0 ? (
                ticket.messages.map((msg) => {
                  const isCustomer = msg.role === 'customer';
                  const isAI       = msg.role === 'ai';
                  const isSystem   = msg.role === 'system';

                  return (
                    <div
                      key={msg.id}
                      className="rounded-lg p-3.5 text-sm leading-relaxed"
                      style={{
                        backgroundColor:
                          isCustomer ? 'var(--bg-elevated)'  :
                          isAI       ? 'var(--bg-elevated)'  :
                          isSystem   ? 'transparent'         : 'var(--bg-hover)',
                        border:
                          isCustomer ? '1px solid var(--border)'           :
                          isAI       ? `1px solid var(--accent-dim)`        :
                          isSystem   ? '1px dashed var(--border)'           : '1px solid var(--border)',
                        marginLeft:  isCustomer ? '0'     : '24px',
                        marginRight: isCustomer ? '24px'  : '0',
                      }}
                    >
                      <div
                        className="flex items-center justify-between mb-2 text-xs font-medium"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        <span style={{ color: isAI ? 'var(--accent)' : 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {isCustomer ? ticket.customer_id :
                           isAI       ? '⚡ ResolveAI' :
                           isSystem   ? 'System' : 'Agent'}
                        </span>
                        <span className="font-mono">
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="whitespace-pre-wrap" style={{ color: isSystem ? 'var(--text-secondary)' : 'var(--text-primary)', fontSize: isSystem ? '0.75rem' : '0.875rem' }}>
                        {msg.content}
                      </p>
                    </div>
                  );
                })
              ) : (
                <div
                  className="rounded-lg p-4 text-sm"
                  style={{
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                >
                  <div className="text-xs mb-2 uppercase font-medium tracking-wider" style={{ color: 'var(--text-muted)' }}>
                    Initial message · {ticket.channel}
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed">{ticket.body}</p>
                </div>
              )}
            </div>

            {/* AI Draft Card */}
            {ticket.draft_response && (
              <DraftCard
                draftResponse={ticket.draft_response}
                intent={ticket.intent}
                confidence={ticket.confidence}
                onApprove={() => onApprove(ticket)}
                onEdit={(edited) => onEdit(ticket, edited)}
                onReject={() => onReject(ticket)}
                canInteract={ticket.status === 'draft_for_review' || ticket.status === 'new'}
              />
            )}

            {/* Tool Actions — only show secondary tools here */}
            <ActionButtons
              ticket={ticket}
              canApprove={false}
              canEdit={false}
              canReject={false}
              onApprove={() => onApprove(ticket)}
              onEdit={(edited) => onEdit(ticket, edited)}
              onReject={() => onReject(ticket)}
              onRefund={(amount) => onRefund(ticket, amount)}
              onOrderStatus={() => onOrderStatus(ticket)}
              onPasswordReset={() => onPasswordReset(ticket)}
            />
          </>
        ) : (
          /* Audit Log */
          <div className="space-y-2.5">
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Autonomous execution trace — captured for enterprise compliance & model telemetry.
            </p>
            {ticket.audit_logs && ticket.audit_logs.length > 0 ? (
              ticket.audit_logs.map((log) => (
                <div
                  key={log.id}
                  className="rounded-lg p-3.5 text-xs space-y-1.5"
                  style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold" style={{ color: 'var(--accent)' }}>
                      {log.action}
                    </span>
                    <span className="font-mono" style={{ color: 'var(--text-muted)' }}>
                      {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    <code style={{ color: 'var(--text-primary)' }}>{log.executed_by}</code>
                    {log.confidence != null && (
                      <span className="ml-2" style={{ color: 'var(--text-muted)' }}>
                        · {(log.confidence * 100).toFixed(1)}% confidence
                      </span>
                    )}
                  </div>
                  {log.payload && (
                    <pre
                      className="rounded p-2 overflow-x-auto"
                      style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-secondary)', fontSize: '10px' }}
                    >
                      {JSON.stringify(log.payload, null, 2)}
                    </pre>
                  )}
                </div>
              ))
            ) : (
              <div
                className="p-8 text-center text-sm rounded-lg"
                style={{ border: '1px dashed var(--border)', color: 'var(--text-muted)' }}
              >
                No audit events yet.
              </div>
            )}
          </div>
        )}
      </div>

      {/* ─── Reply Composer ───────────────────── */}
      <form
        onSubmit={handleSendReply}
        className="px-4 py-3 flex gap-2 items-center"
        style={{ borderTop: '1px solid var(--border)', backgroundColor: 'var(--bg-surface)' }}
      >
        <input
          id="input-agent-reply"
          type="text"
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          placeholder={`Reply to ${ticket.customer_id} via ${ticket.channel}…`}
          className="flex-1 px-3 py-2 text-sm rounded-md"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
        />
        <button
          id="btn-send-agent-reply"
          type="submit"
          disabled={!replyText.trim()}
          className="px-4 py-2 text-sm font-medium rounded-md text-white transition-opacity"
          style={{
            backgroundColor: 'var(--accent)',
            opacity: replyText.trim() ? 1 : 0.4,
            cursor: replyText.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};
