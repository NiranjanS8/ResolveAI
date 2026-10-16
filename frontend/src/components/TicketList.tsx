import React, { useState, useMemo } from 'react';
import { type Ticket, type Channel } from '../api/tickets';
import { Icon } from './Icon';

interface TicketListProps {
  tickets: Ticket[];
  selectedTicketId?: string | null;
  onSelectTicket: (ticket: Ticket) => void;
  filterChannel?: 'all' | Channel;
  onFilterChannelChange?: (channel: 'all' | Channel) => void;
}

const formatRelativeTime = (isoString: string) => {
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h`;
    return `${Math.floor(diffHours / 24)}d`;
  } catch { return ''; }
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft_for_review: { label: 'Needs review', color: 'var(--yellow)',  bg: 'var(--yellow-dim)' },
  auto_resolved:    { label: 'Auto-resolved', color: 'var(--green)',   bg: 'var(--green-dim)'  },
  escalated:        { label: 'Escalated',     color: 'var(--red)',     bg: 'var(--red-dim)'    },
  resolved:         { label: 'Resolved',      color: 'var(--green)',   bg: 'var(--green-dim)'  },
  new:              { label: 'New',           color: 'var(--accent)',  bg: 'var(--accent-dim)' },
};

const URGENCY_DOT: Record<string, string> = {
  critical: 'var(--red)',
  high:     'var(--yellow)',
  medium:   'var(--text-muted)',
  low:      'var(--text-muted)',
};

const STATUS_FILTERS = [
  { id: 'all',              label: 'All'      },
  { id: 'draft_for_review', label: 'Review'   },
  { id: 'auto_resolved',    label: 'Resolved' },
  { id: 'escalated',        label: 'Escalated'},
];

export const TicketList: React.FC<TicketListProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
  filterChannel = 'all',
  onFilterChannelChange,
}) => {
  const [searchTerm, setSearchTerm]     = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filtered = useMemo(() => {
    return tickets.filter((t) => {
      const matchChannel = filterChannel === 'all' || t.channel === filterChannel;
      const matchStatus  = statusFilter === 'all' || t.status === statusFilter;
      const term         = searchTerm.toLowerCase().trim();
      const matchSearch  =
        !term ||
        t.subject.toLowerCase().includes(term) ||
        t.customer_id.toLowerCase().includes(term) ||
        (t.intent && t.intent.toLowerCase().includes(term));
      return matchChannel && matchStatus && matchSearch;
    });
  }, [tickets, filterChannel, statusFilter, searchTerm]);

  const pendingCount = tickets.filter(t => t.status === 'draft_for_review').length;

  return (
    <div
      className="flex flex-col h-full rounded-lg overflow-hidden"
      style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)' }}
    >
      {/* ── Header ─────────────────────────────── */}
      <div className="p-3 space-y-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
        {/* Title row */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Queue
          </span>
          {pendingCount > 0 && (
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium font-mono"
              style={{ backgroundColor: 'var(--yellow-dim)', color: 'var(--yellow)' }}
            >
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Search */}
        <div className="relative">
          <Icon
            name="search"
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--text-muted)]"
          />
          <input
            id="ticket-search-input"
            type="text"
            placeholder="Search tickets…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--text-muted)' }}
            >
              <Icon name="close" size={13} />
            </button>
          )}
        </div>

        {/* Status filter pills */}
        <div className="flex items-center gap-1">
          {STATUS_FILTERS.map((f) => {
            const active = statusFilter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => setStatusFilter(f.id)}
                className="px-2.5 py-1 rounded-md text-xs font-medium transition-all"
                style={{
                  backgroundColor: active ? 'var(--accent-dim)' : 'transparent',
                  color:           active ? 'var(--accent)'      : 'var(--text-secondary)',
                  border:          active ? '1px solid rgba(88,166,255,.25)' : '1px solid transparent',
                }}
              >
                {f.label}
              </button>
            );
          })}

          {onFilterChannelChange && (
            <div className="ml-auto flex items-center gap-0.5 rounded-md p-0.5" style={{ backgroundColor: 'var(--bg-elevated)' }}>
              {(['all', 'chat', 'email'] as const).map((ch) => (
                <button
                  key={ch}
                  onClick={() => onFilterChannelChange(ch)}
                  className="px-2 py-0.5 rounded text-xs capitalize transition-all"
                  style={{
                    backgroundColor: filterChannel === ch ? 'var(--bg-surface)' : 'transparent',
                    color: filterChannel === ch ? 'var(--text-primary)' : 'var(--text-muted)',
                    fontWeight: filterChannel === ch ? '500' : '400',
                  }}
                >
                  {ch}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Ticket rows ────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="p-10 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
            No tickets match your filters.
          </div>
        ) : (
          filtered.map((ticket) => {
            const isSelected = selectedTicketId === ticket.id;
            const cfg        = STATUS_CONFIG[ticket.status] || STATUS_CONFIG.new;
            const urgDot     = URGENCY_DOT[ticket.urgency || 'low'];

            return (
              <div
                key={ticket.id}
                id={`ticket-row-${ticket.id}`}
                onClick={() => onSelectTicket(ticket)}
                className="relative cursor-pointer transition-colors"
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  backgroundColor: isSelected ? 'var(--bg-hover)' : 'transparent',
                  borderLeft: isSelected ? '2px solid var(--accent)' : '2px solid transparent',
                }}
              >
                {/* Row top: customer + channel badge + time */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                      {ticket.customer_id}
                    </span>
                    <span
                      className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-sm whitespace-nowrap"
                      style={{
                        backgroundColor: ticket.channel === 'email' ? 'var(--green-dim)' : 'var(--accent-dim)',
                        color: ticket.channel === 'email' ? 'var(--green)' : 'var(--accent)',
                        fontWeight: '500',
                      }}
                    >
                      {ticket.channel}
                    </span>
                  </div>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {formatRelativeTime(ticket.created_at)}
                  </span>
                </div>

                {/* Subject */}
                <div
                  className="text-sm font-medium mb-1.5 line-clamp-1"
                  style={{ color: 'var(--text-primary)' }}
                  title={ticket.subject}
                >
                  {ticket.subject}
                </div>

                {/* Bottom: status + urgency dot + confidence */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {/* Urgency dot */}
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: urgDot }}
                      title={`Urgency: ${ticket.urgency}`}
                    />
                    {/* Status badge */}
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap"
                      style={{ backgroundColor: cfg.bg, color: cfg.color }}
                    >
                      {cfg.label}
                    </span>
                    {/* Intent tag */}
                    {ticket.intent && (
                      <span
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded whitespace-nowrap"
                        style={{
                          backgroundColor: 'var(--bg-elevated)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        {ticket.intent}
                      </span>
                    )}
                  </div>

                  {/* Confidence */}
                  {ticket.confidence != null && (
                    <span
                      className="text-xs font-mono"
                      style={{
                        color:
                          ticket.confidence >= 0.9 ? 'var(--green)' :
                          ticket.confidence >= 0.75 ? 'var(--yellow)' : 'var(--red)',
                      }}
                    >
                      {Math.round(ticket.confidence * 100)}%
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Footer ─────────────────────────────── */}
      <div
        className="px-4 py-2 flex items-center justify-between text-xs font-mono"
        style={{ borderTop: '1px solid var(--border)', color: 'var(--text-muted)' }}
      >
        <span>{filtered.length} / {tickets.length} tickets</span>
        <span className="inline-flex items-center gap-1.5" style={{ color: 'var(--green)' }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--green)' }} />
          live
        </span>
      </div>
    </div>
  );
};