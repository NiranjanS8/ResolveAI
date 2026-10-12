import React from 'react';
import './index.css';

/**
 * Phase 6-7: Approve/Edit/Reject buttons for draft reviews
 * Per design.md:
 * - Primary action (Approve): filled --accent background, white text, --radius corners
 * - Secondary (Edit): outline only, --border-hairline border, --text-primary text
 * - Destructive (Reject): outline only, --status-low border and text -- never filled red
 */
interface ActionButtonsProps {
  ticket: any;
  canApprove: boolean;
  canEdit: boolean;
  canReject: boolean;
  onApprove: () => void;
  onEdit: (editedDraft: string) => void;
  onReject: () => void;
}

export const ActionButtons: React.FC<ActionButtonsProps> = ({
  ticket,
  canApprove,
  canEdit,
  canReject,
  onApprove,
  onEdit,
  onReject,
}) => {
  const statusColors: Record<string, string> = {
    new: 'var(--status-medium)',
    auto_resolved: 'var(--status-high)',
    draft_for_review: 'var(--status-medium)',
    escalated: 'var(--status-low)',
    resolved: 'var(--status-high)',
  };

  return (
    <div className="flex gap-2 mt-3" style={{ fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif" }}>
      {/* Approve Button - Primary: filled accent */}
      {canApprove && (
        <button
          onClick={onApprove}
          disabled={!ticket.draft_response}
          style={{
            backgroundColor: 'var(--accent)',
            color: 'white',
            borderRadius: '4px',
            padding: '8px 16px',
            fontSize: '0.875rem',
            fontWeight: '500',
            transition: 'opacity 0.2s',
            opacity: ticket.draft_response ? 1 : 0.6,
          }}
        >
          Approve
        </button>
      )}

      {/* Edit Button - Secondary: outline */}
      {canEdit && ticket.draft_response && (
        <button
          onClick={() => {
            const edited = prompt('Edit the draft:', ticket.draft_response);
            if (edited !== null && edited.trim()) {
              onEdit(edited.trim());
            }
          }}
          disabled={!ticket.draft_response}
          style={{
            border: '1px solid var(--border-hairline)',
            color: 'var(--text-primary)',
            borderRadius: '4px',
            padding: '8px 16px',
            fontSize: '0.875rem',
            fontWeight: '500',
            backgroundColor: 'var(--bg-surface)',
            transition: 'opacity 0.2s',
          }}
        >
          Edit
        </button>
      )}

      {/* Reject Button - Destructive: --status-low outline */}
      {canReject && (
        <button
          onClick={onReject}
          style={{
            border: '1px solid var(--status-low)',
            color: 'var(--status-low)',
            borderRadius: '4px',
            padding: '8px 16px',
            fontSize: '0.875rem',
            fontWeight: '500',
            transition: 'opacity 0.2s',
          }}
        >
          Reject
        </button>
      )}
    </div>
  );
}