import React, { useState, useEffect } from 'react';
import './index.css';
import { TicketStatusBadge } from './TicketStatusBadge';

/**
 * Phase 1-4: Ticket table listing with status-colored borders
 * Per design.md: "Rows, not cards. 1px --border-hairline between rows, no shadows,
 * no rounded-card containers around each ticket. Row height generous (44-48px),
 * left-aligned columns: status border → subject → intent tag → timestamp"
 */
interface TicketListProps {
  tickets: any[];
  onDetail?: (ticket: any) => void;
  onApprove?: (ticket: any) => void;
  onEdit?: (ticket: any) => void;
  onReject?: (ticket: any) => void;
  canEdit?: boolean;
}

export const TicketList: React.FC<TicketListProps> = ({
  tickets,
  onDetail,
  onApprove,
  onEdit,
  onReject,
  canEdit = false,
}) => {
  const [loading, setLoading] = useState(false);

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--border-hairline)] bg-[var(--bg-surface-hover)]">
            <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)', borderRight: '1px solid var(--border-hairline)' }}>
              Status
            </th>
            <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)', borderRight: '1px solid var(--border-hairline)' }}>
              Subject
            </th>
            <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              Customer
            </th>
            <th className="px-4 py-3 text-left text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              Created
            </th>
          </thead>
          <tbody>
            {tickets.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-[var(--text-secondary)]">
                  No tickets yet. Submit one above.
                </td>
              </tr>
            ) : (
              tickets.map((ticket) => (
                <tr
                  key={ticket.id}
                  className="border-t hover:bg-[var(--bg-surface-hover)]"
                  style={{ borderColor: 'var(--border-hairline)' }}
                >
                  <td className="px-4 py-3">
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2',
                        ...(canEdit && {
                          cursor: canEdit ? 'pointer' : 'default',
                        }),
                      }}
                      onClick={canEdit && onApprove ? () => onApprove(ticket) : undefined}
                    >
                      <TicketStatusBadge
                        status={ticket.status}
                        showBorder={canEdit}
                      />
                      <span className="text-[var(--text-secondary)] text-sm">
                        {ticket.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        onDetail?.(ticket);
                      }
                      style={{
                        color: 'var(--primary)',
                        textDecoration: 'none',
                        fontWeight: '500',
                        fontSize: '0.875rem',
                      }}
                    >
                      {ticket.subject}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[var(--text-secondary)] text-sm">
                      {ticket.customer_id}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[var(--text-secondary)] text-sm truncate">
                      {new Date(ticket.created_at).toLocaleString()}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}