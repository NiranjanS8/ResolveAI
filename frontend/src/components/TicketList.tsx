import React, { useMemo, useState } from 'react';
import { type Channel, type Ticket } from '../api/tickets';
import { Icon } from './Icon';
import {
  channelLabel,
  classifierCertainty,
  formatRelativeTime,
  formatScore,
  intentLabel,
  statusColor,
  statusLabel,
} from '../lib/ticketDisplay';

interface TicketListProps {
  tickets: Ticket[];
  selectedTicketId?: string | null;
  onSelectTicket: (ticket: Ticket) => void;
  filterChannel?: 'all' | Channel;
  onFilterChannelChange?: (channel: 'all' | Channel) => void;
}

const STATUS_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'draft_for_review', label: 'Needs review' },
  { id: 'auto_resolved', label: 'Auto-resolved' },
  { id: 'escalated', label: 'Escalated' },
];

const CHANNEL_FILTERS: Array<{ id: 'all' | Channel; label: string }> = [
  { id: 'all', label: 'All channels' },
  { id: 'email', label: 'Email' },
  { id: 'chat', label: 'Chat' },
];

/** Underline-only filter control: primary text plus a 2px underline, never accent. */
const FilterButton: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({
  active,
  onClick,
  children,
}) => (
  <button
    type="button"
    onClick={onClick}
    className="text-[12px] font-medium whitespace-nowrap"
    style={{
      color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
      borderBottom: `2px solid ${active ? 'var(--text-primary)' : 'transparent'}`,
      paddingBottom: 2,
    }}
  >
    {children}
  </button>
);

export const TicketList: React.FC<TicketListProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
  filterChannel = 'all',
  onFilterChannelChange,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filtered = useMemo(() => {
    const term = searchTerm.toLowerCase().trim();
    return tickets.filter((ticket) => {
      const matchChannel = filterChannel === 'all' || ticket.channel === filterChannel;
      const matchStatus = statusFilter === 'all' || ticket.status === statusFilter;
      const matchSearch =
        !term ||
        ticket.subject.toLowerCase().includes(term) ||
        ticket.customer_id.toLowerCase().includes(term) ||
        (ticket.intent ?? '').toLowerCase().includes(term);
      return matchChannel && matchStatus && matchSearch;
    });
  }, [tickets, filterChannel, statusFilter, searchTerm]);

  const isFiltered = filtered.length !== tickets.length;

  return (
    <div
      className="flex flex-col h-full"
      style={{ borderRight: '1px solid var(--border-hairline)' }}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="px-4 pt-3 pb-2.5 space-y-3" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
        <div className="relative">
          <span
            className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
            style={{ color: 'var(--text-secondary)', lineHeight: 0 }}
          >
            <Icon name="search" size={14} />
          </span>
          <input
            id="ticket-search-input"
            type="text"
            placeholder="Search subject, customer, intent"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-7 py-1.5 text-[13px]"
            style={{
              backgroundColor: 'var(--bg-base)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--radius)',
              color: 'var(--text-primary)',
            }}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--text-secondary)', lineHeight: 0 }}
            >
              <Icon name="close" size={13} />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {STATUS_FILTERS.map((filter) => (
            <FilterButton
              key={filter.id}
              active={statusFilter === filter.id}
              onClick={() => setStatusFilter(filter.id)}
            >
              {filter.label}
            </FilterButton>
          ))}
        </div>

        {onFilterChannelChange && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {CHANNEL_FILTERS.map((filter) => (
              <FilterButton
                key={filter.id}
                active={filterChannel === filter.id}
                onClick={() => onFilterChannelChange(filter.id)}
              >
                {filter.label}
              </FilterButton>
            ))}
          </div>
        )}
      </div>

      {/* ── Rows ───────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="px-4 py-10 text-center text-[13px]" style={{ color: 'var(--text-secondary)' }}>
            {tickets.length === 0 ? 'No tickets in the queue.' : 'No tickets match these filters.'}
          </p>
        ) : (
          filtered.map((ticket) => {
            const isSelected = selectedTicketId === ticket.id;
            const certainty = classifierCertainty(ticket);
            return (
              <button
                key={ticket.id}
                id={`ticket-row-${ticket.id}`}
                onClick={() => onSelectTicket(ticket)}
                className="w-full text-left block"
                style={{
                  padding: '10px 16px 10px 13px',
                  borderBottom: '1px solid var(--border-hairline)',
                  /* The row's single colour signal: the confidence tier. */
                  borderLeft: `3px solid ${statusColor(ticket.status)}`,
                  backgroundColor: isSelected ? 'var(--bg-surface-hover)' : 'transparent',
                }}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className="text-[13px] font-medium truncate"
                    style={{ color: 'var(--text-primary)' }}
                    title={ticket.subject}
                  >
                    {ticket.subject}
                  </span>
                  <span className="text-[12px] font-mono shrink-0" style={{ color: 'var(--text-secondary)' }}>
                    {formatRelativeTime(ticket.created_at)}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 mt-1">
                  <span className="flex items-center gap-3 min-w-0 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                    <span className="whitespace-nowrap">{statusLabel(ticket.status)}</span>
                    {intentLabel(ticket.intent) && (
                      <span className="truncate">{intentLabel(ticket.intent)}</span>
                    )}
                    <span className="flex items-center gap-1 shrink-0" title={channelLabel(ticket.channel)}>
                      <Icon name={ticket.channel === 'email' ? 'mail' : 'chat'} size={13} />
                      <span className="sr-only">{channelLabel(ticket.channel)}</span>
                    </span>
                  </span>
                  <span className="text-[12px] font-mono shrink-0" style={{ color: 'var(--text-secondary)' }}>
                    {formatScore(certainty)}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* ── Footer ─────────────────────────────────────────── */}
      <div
        className="px-4 py-2 flex items-center justify-between text-[12px]"
        style={{ borderTop: '1px solid var(--border-hairline)', color: 'var(--text-secondary)' }}
      >
        <span className="font-mono">
          Showing {filtered.length} of {tickets.length}
        </span>
        {isFiltered && (
          <button
            onClick={() => {
              setStatusFilter('all');
              setSearchTerm('');
              onFilterChannelChange?.('all');
            }}
            className="font-medium"
            style={{ color: 'var(--text-primary)' }}
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
};
