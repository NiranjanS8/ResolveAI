import React from 'react';
import './index.css';

/**
 * Phase 1-3: Status badge with 3px left border in status color
 * Per design.md: "Not a filled pill. A 3px solid left border in the status color
 * plus plain-sentence-case text label"
 */
interface TicketStatusBadgeProps {
  status: string;
  showBorder?: boolean;
}

const statusColors: Record<string, string> = {
  new: 'var(--status-medium)',
  auto_resolved: 'var(--status-high)',
  draft_for_review: 'var(--status-medium)',
  escalated: 'var(--status-low)',
  resolved: 'var(--status-high)',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  auto_resolved: 'Auto-resolved',
  draft_for_review: 'Needs review',
  escalated: 'Escalated',
  resolved: 'Resolved',
};

export const TicketStatusBadge: React.FC<TicketStatusBadgeProps> = ({
  status,
  showBorder = true,
}) => {
  const color = statusColors[status] || 'var(--text-secondary)';
  const label = statusLabels[status] || status;

  return (
    <span
      style={{
        ...(showBorder && {
          borderLeft: '3px solid',
          borderColor: color,
          paddingLeft: '8px',
        }),
        fontSize: '0.875rem',
        fontWeight: '500',
        color: color,
      }}
    >
      {label}
    </span>
  );
};