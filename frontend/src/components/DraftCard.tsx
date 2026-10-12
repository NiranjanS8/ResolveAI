import React from 'react';
import './index.css';

/**
 * Phase 5-6: AI draft display card
 * Per design.md: "AI draft panel: visually distinct from a human-written response:
 * a thin --accent left border (not the confidence-status border) with a small
 * monospace label 'AI draft' in --text-secondary, not a badge."
 */
interface DraftCardProps {
  draftResponse: string | null | undefined;
  intent: string | null | undefined;
  onApprove?: () => void;
  onEdit?: (edited: string) => void;
  onReject?: () => void;
  canInteract?: boolean;
}

export const DraftCard: React.FC<DraftCardProps> = ({
  draftResponse,
  intent,
  onApprove,
  onEdit,
  onReject,
  canInteract = true,
}) => {
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

  if (!draftResponse) {
    return null;
  }

  return (
    <div
      style={{
        borderLeft: '3px solid var(--accent)',
        padding: '12px 16px',
        margin: '16px 0',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: '4px',
        fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
      }}
    >
      <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
        <span style={{ fontFamily: "'IBM Plex Mono', 'SF Mono', Consolas, monospace", fontSize: '0.75rem', color: 'var(--text-secondary)' }}>AI draft</span>
        <span style={{ marginLeft: '4px' }}>{statusLabels[intent || '']}</span>
      </div>
      <p
        style={{
          margin: 0,
          fontSize: '0.875rem',
          lineHeight: '1.5',
          color: 'var(--text-primary)',
        }}
      >
        {draftResponse}
      </p>
      {canInteract && (
        <div
          style={{
            marginTop: '8px',
            display: 'flex',
            gap: '8px',
          }}
        >
          {canApprove && (
            <button
              onClick={onApprove}
              style={{
                flex: 1,
                backgroundColor: 'var(--accent)',
                color: 'white',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '0.75rem',
                fontWeight: '500',
              }}
            >
              Approve
            </button>
          )}
          {onEdit && (
            <button
              onClick={() => {
                const edited = prompt('Edit draft:', draftResponse);
                if (edited !== null && edited.trim()) {
                  onEdit(edited.trim());
                }
              }}
              style={{
                flex: 1,
                border: '1px solid var(--border-hairline)',
                color: 'var(--text-primary)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '0.75rem',
                transition: 'opacity 0.2s',
                opacity: draftResponse.trim() ? 1 : 0.6,
              }}
            >
              Edit
            </button>
          )}
          {onReject && (
            <button
              onClick={onReject}
              style={{
                flex: 1,
                border: '1px solid var(--status-low)',
                color: 'var(--status-low)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '0.75rem',
              }}
            >
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}