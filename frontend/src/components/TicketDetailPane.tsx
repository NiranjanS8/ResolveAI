import React, { useState } from 'react';
import { type Ticket } from '../api/tickets';
import { DraftCard } from './DraftCard';
import { ActionButtons } from './ActionButtons';
import { Icon } from './Icon';
import {
  REFUND_INR_CAP,
  channelLabel,
  classifierCertainty,
  copyToClipboard,
  formatClockTime,
  formatScore,
  formatTimestamp,
  intentLabel,
  retrievalRelevance,
  routingScore,
  sentimentLabel,
  shortId,
  statusColor,
  statusLabel,
  statusTier,
  thresholdsFor,
  tierColor,
  urgencyLabel,
} from '../lib/ticketDisplay';

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
  isLoading?: boolean;
  detailError?: string | null;
  onRetryDetail?: () => void;
}

type DetailTab = 'decision' | 'conversation' | 'audit';

const Fact: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-baseline gap-2">
    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
      {label}
    </span>
    <span className="text-[12px]" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
  </div>
);

const TraceRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-baseline justify-between gap-4 py-1.5" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
      {label}
    </span>
    <span className="text-[13px] font-mono text-right" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
  </div>
);

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
  isLoading = false,
  detailError = null,
  onRetryDetail,
}) => {
  const [replyText, setReplyText] = useState('');
  const [activeTab, setActiveTab] = useState<DetailTab>('decision');
  const [copied, setCopied] = useState(false);

  const handleSendReply = (e: React.FormEvent) => {
    e.preventDefault();
    const text = replyText.trim();
    if (!text) return;
    onSendMessage(ticket, text);
    setReplyText('');
  };

  const handleCopyId = async () => {
    if (await copyToClipboard(ticket.id)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  };

  const tier = statusTier(ticket.status);
  const certainty = classifierCertainty(ticket);
  const relevance = retrievalRelevance(ticket.retrieved_context);
  const score = routingScore(ticket);
  const { high, medium } = thresholdsFor(ticket.intent);
  const sources = ticket.retrieved_context ?? [];
  const messages = ticket.messages ?? [];
  const auditLogs = ticket.audit_logs ?? [];

  // The list endpoint omits messages, audit log and sources. Until the detail
  // arrives, those sections hold nothing — so they must not be rendered as if
  // they were empty on purpose.
  const detailReady = !isLoading && !detailError;

  const TABS: Array<{ id: DetailTab; label: string; count?: number }> = [
    { id: 'decision', label: 'Decision trace' },
    { id: 'conversation', label: 'Conversation', count: detailReady ? messages.length : undefined },
    { id: 'audit', label: 'Audit log', count: detailReady ? auditLogs.length : undefined },
  ];

  const guardrails: Array<{ label: string; value: string }> = [
    {
      label: 'Refund cap',
      value:
        ticket.intent === 'refund' || ticket.intent === 'billing'
          ? `₹${REFUND_INR_CAP.toLocaleString('en-IN')} — applies to this ticket`
          : `₹${REFUND_INR_CAP.toLocaleString('en-IN')} — not applicable`,
    },
    {
      label: 'Action allow-list',
      value: 'Refund, order status, password reset only',
    },
    {
      label: 'Auto-resolve gate',
      value:
        score === null
          ? 'No retrieval signal — never auto-resolves'
          : `${formatScore(score)} vs ${formatScore(high)} — ${score >= high ? 'met' : 'not met'}`,
    },
    {
      label: 'Human review',
      value: ticket.status === 'draft_for_review' ? 'Required before send' : 'Not required',
    },
  ];

  return (
    <div className="flex flex-col h-full animate-slide-in">
      {/* ─── Header ─────────────────────────────────────────── */}
      <div className="px-5 pt-4 pb-3" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-3 min-w-0">
            <span className="flex items-center gap-1" style={{ color: 'var(--text-secondary)' }}>
              <span className="text-[13px] font-mono" style={{ color: 'var(--text-primary)' }}>
                #{shortId(ticket.id)}
              </span>
              <button
                onClick={handleCopyId}
                aria-label="Copy full ticket id"
                title={copied ? 'Copied' : 'Copy full ticket id'}
                className="p-0.5"
              >
                <Icon name={copied ? 'check' : 'copy'} size={12} />
              </button>
            </span>

            <span className="flex items-center gap-1.5 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              <Icon name={ticket.channel === 'email' ? 'mail' : 'chat'} size={13} />
              {channelLabel(ticket.channel)}
            </span>

            {/* Status: 3px left border strip + plain sentence-case label */}
            <span
              className="text-[12px] pl-2"
              style={{ borderLeft: `3px solid ${statusColor(ticket.status)}`, color: 'var(--text-secondary)' }}
            >
              {statusLabel(ticket.status)}
            </span>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
              {formatTimestamp(ticket.created_at)}
            </span>
            {onClose && (
              <button
                onClick={onClose}
                aria-label="Close ticket detail"
                style={{ color: 'var(--text-secondary)', lineHeight: 0 }}
              >
                <Icon name="close" size={14} />
              </button>
            )}
          </div>
        </div>

        <h2 className="text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>
          {ticket.subject}
        </h2>
        <div className="text-[12px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
          {ticket.customer_id}
        </div>
      </div>

      {/* ─── Facts strip — one fact per element, no chips ───── */}
      <div
        className="px-5 py-2.5 flex flex-wrap items-center gap-x-6 gap-y-1.5"
        style={{ borderBottom: '1px solid var(--border-hairline)' }}
      >
        <Fact label="Intent" value={intentLabel(ticket.intent) ?? 'Unclassified'} />
        <Fact label="Urgency" value={urgencyLabel(ticket.urgency)} />
        <Fact label="Sentiment" value={sentimentLabel(ticket.sentiment)} />
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
            Confidence
          </span>
          <div className="conf-bar-track w-20">
            <div
              className="conf-bar-fill"
              style={{
                width: `${(certainty ?? 0) * 100}%`,
                /* Colour comes from the tier the router assigned, so the bar can
                   never disagree with the status. */
                backgroundColor: tierColor(tier),
              }}
            />
          </div>
          <span className="text-[13px] font-mono font-semibold" style={{ color: tierColor(tier) }}>
            {formatScore(certainty)}
          </span>
        </div>
      </div>

      {/* ─── Tabs ───────────────────────────────────────────── */}
      <div className="flex items-center px-5 gap-6" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="py-2.5 text-[12px] font-medium"
              style={{
                color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                borderBottom: `2px solid ${active ? 'var(--text-primary)' : 'transparent'}`,
              }}
            >
              {tab.label}
              {tab.count !== undefined ? ` (${tab.count})` : ''}
            </button>
          );
        })}
      </div>

      {/* ─── Content ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {isLoading && (
          <div className="h-full flex flex-col items-center justify-center gap-2">
            <div
              className="w-5 h-5 rounded-full border-2 animate-spin"
              style={{ borderColor: 'var(--border-hairline)', borderTopColor: 'var(--text-primary)' }}
            />
            <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              Loading ticket detail
            </span>
          </div>
        )}

        {!isLoading && detailError && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-6">
            <span style={{ color: 'var(--status-low)' }}>
              <Icon name="alert" size={20} />
            </span>
            <p className="text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>
              Could not load this ticket's detail
            </p>
            <p className="text-[12px] font-mono max-w-sm" style={{ color: 'var(--text-secondary)' }}>
              {detailError}
            </p>
            <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              The queue retries every 10 seconds.
            </p>
            {onRetryDetail && (
              <button
                onClick={onRetryDetail}
                className="px-3 h-6 text-[12px] font-medium"
                style={{
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 'var(--radius)',
                }}
              >
                Retry
              </button>
            )}
          </div>
        )}

        {detailReady && activeTab === 'decision' && (
          <>
            <section>
              <h3 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                Confidence breakdown
              </h3>
              <TraceRow label="Classifier certainty" value={formatScore(certainty)} />
              <TraceRow label="Retrieval relevance (top chunk)" value={formatScore(relevance)} />
              <TraceRow label="Final score" value={formatScore(score)} />
              <TraceRow label="Thresholds" value={`auto ≥ ${formatScore(high)}  review ≥ ${formatScore(medium)}`} />
            </section>

            <section>
              <h3 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                Sources used
              </h3>
              {sources.length > 0 ? (
                <ul>
                  {sources.map((chunk, index) => (
                    <li
                      key={chunk.id ?? index}
                      className="flex items-baseline justify-between gap-4 py-1.5"
                      style={{ borderBottom: '1px solid var(--border-hairline)' }}
                    >
                      <span className="text-[12px] truncate" style={{ color: 'var(--text-primary)' }}>
                        {chunk.doc_title || chunk.source_id || 'Untitled article'}
                      </span>
                      <span className="text-[12px] font-mono shrink-0" style={{ color: 'var(--text-secondary)' }}>
                        {formatScore(Number(chunk.score ?? 0))}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                  No knowledge-base article matched this ticket.
                </p>
              )}
            </section>

            <section>
              <h3 className="text-[13px] font-semibold mb-2 flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                <Icon name="shield" size={13} />
                Guardrails checked
              </h3>
              <TraceRow label={guardrails[0].label} value={guardrails[0].value} />
              <TraceRow label={guardrails[1].label} value={guardrails[1].value} />
              <TraceRow label={guardrails[2].label} value={guardrails[2].value} />
              <TraceRow label={guardrails[3].label} value={guardrails[3].value} />
            </section>

            {ticket.draft_response && (
              <DraftCard
                draftResponse={ticket.draft_response}
                onApprove={() => onApprove(ticket)}
                onEdit={(edited) => onEdit(ticket, edited)}
                onReject={() => onReject(ticket)}
                canInteract={ticket.status === 'draft_for_review' || ticket.status === 'new'}
              />
            )}

            <ActionButtons
              ticket={ticket}
              onRefund={(amount) => onRefund(ticket, amount)}
              onOrderStatus={() => onOrderStatus(ticket)}
              onPasswordReset={() => onPasswordReset(ticket)}
            />
          </>
        )}

        {detailReady && activeTab === 'conversation' && (
          <div>
            {messages.length > 0 ? (
              messages.map((message) => {
                const isCustomer = message.role === 'customer';
                return (
                  <article
                    key={message.id}
                    className="py-3"
                    style={{
                      borderBottom: '1px solid var(--border-hairline)',
                      borderLeft: isCustomer ? 'none' : '3px solid ' + (message.role === 'agent' ? 'var(--border-hairline)' : 'var(--accent)'),
                      paddingLeft: isCustomer ? 0 : 12,
                    }}
                  >
                    <div className="flex items-center justify-between gap-3 mb-1.5">
                      <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                        {isCustomer ? ticket.customer_id : message.role === 'agent' ? 'Agent' : message.role === 'ai' ? 'AI draft' : 'System'}
                      </span>
                      <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {formatClockTime(message.created_at)}
                      </span>
                    </div>
                    <p className="text-[13px] whitespace-pre-wrap leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                      {message.content}
                    </p>
                  </article>
                );
              })
            ) : (
              <article className="py-3">
                <div className="flex items-center justify-between gap-3 mb-1.5">
                  <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                    {ticket.customer_id}
                  </span>
                  <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {formatClockTime(ticket.created_at)}
                  </span>
                </div>
                <p className="text-[13px] whitespace-pre-wrap leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  {ticket.body}
                </p>
              </article>
            )}
          </div>
        )}

        {detailReady && activeTab === 'audit' && (
          <div>
            {auditLogs.length > 0 ? (
              auditLogs.map((log) => (
                <div
                  key={log.id}
                  className="py-3"
                  style={{ borderBottom: '1px solid var(--border-hairline)' }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[13px] font-mono" style={{ color: 'var(--text-primary)' }}>
                      {log.action}
                    </span>
                    <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  <div className="text-[12px] font-mono mt-1 flex items-center gap-3" style={{ color: 'var(--text-secondary)' }}>
                    <span>{log.executed_by ?? 'system'}</span>
                    {log.confidence != null && <span>{formatScore(Number(log.confidence))}</span>}
                  </div>
                  {log.payload && (
                    <pre
                      className="mt-2 p-2 overflow-x-auto text-[12px]"
                      style={{
                        backgroundColor: 'var(--bg-base)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {JSON.stringify(log.payload, null, 2)}
                    </pre>
                  )}
                </div>
              ))
            ) : (
              <p className="py-6 text-center text-[13px]" style={{ color: 'var(--text-secondary)' }}>
                No audit events recorded for this ticket.
              </p>
            )}
          </div>
        )}
      </div>

      {/* ─── Reply composer ─────────────────────────────────── */}
      <form
        onSubmit={handleSendReply}
        className="px-4 py-3 flex gap-2 items-center"
        style={{ borderTop: '1px solid var(--border-hairline)' }}
      >
        <input
          id="input-agent-reply"
          type="text"
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          placeholder={`Reply to ${ticket.customer_id}`}
          className="flex-1 px-3 py-1.5 text-[13px]"
          style={{
            backgroundColor: 'var(--bg-base)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 'var(--radius)',
            color: 'var(--text-primary)',
          }}
        />
        <button
          id="btn-send-agent-reply"
          type="submit"
          disabled={!replyText.trim()}
          className="px-3.5 py-1.5 text-[13px] font-medium"
          style={{
            backgroundColor: replyText.trim() ? 'var(--accent)' : 'transparent',
            color: replyText.trim() ? 'var(--on-accent)' : 'var(--text-secondary)',
            border: replyText.trim() ? 'none' : '1px solid var(--border-hairline)',
            borderRadius: 'var(--radius)',
            cursor: replyText.trim() ? 'pointer' : 'not-allowed',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
};
