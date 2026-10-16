import React, { useState } from 'react';
import { Icon } from './Icon';

interface DraftCardProps {
  draftResponse: string | null | undefined;
  onApprove?: () => void;
  onEdit?: (edited: string) => void;
  onReject?: () => void;
  canInteract?: boolean;
}

/**
 * The AI-generated reply. A thin accent left border plus a monospace "AI draft"
 * label is the only thing marking it as machine-written — no badge, no fill.
 */
export const DraftCard: React.FC<DraftCardProps> = ({
  draftResponse,
  onApprove,
  onEdit,
  onReject,
  canInteract = true,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(draftResponse || '');

  if (!draftResponse) return null;

  const handleSaveEdit = () => {
    if (editedText.trim() && onEdit) {
      onEdit(editedText.trim());
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditedText(draftResponse);
    setIsEditing(false);
  };

  const secondaryButton: React.CSSProperties = {
    border: '1px solid var(--border-hairline)',
    borderRadius: 'var(--radius)',
    color: 'var(--text-primary)',
    backgroundColor: 'transparent',
  };

  return (
    <section
      aria-label="AI draft"
      className="animate-slide-in"
      style={{
        backgroundColor: 'var(--bg-base)',
        borderLeft: '3px solid var(--accent)',
        borderRadius: 'var(--radius)',
      }}
    >
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <Icon name="sparkle" size={13} />
        <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
          AI draft
        </span>
      </div>

      <div className="px-4 pb-4">
        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={5}
              className="w-full p-3 text-[13px] leading-relaxed"
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--accent)',
                borderRadius: 'var(--radius)',
                color: 'var(--text-primary)',
                resize: 'vertical',
              }}
              placeholder="Edit the draft before sending"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={handleCancelEdit}
                className="px-3 py-1.5 text-[13px] font-medium"
                style={secondaryButton}
              >
                Cancel
              </button>
              <button
                id="btn-save-draft"
                onClick={handleSaveEdit}
                className="px-3.5 py-1.5 text-[13px] font-medium"
                style={{
                  backgroundColor: 'var(--accent)',
                  color: 'var(--on-accent)',
                  borderRadius: 'var(--radius)',
                }}
              >
                Save and send
              </button>
            </div>
          </div>
        ) : (
          <>
            <p
              className="text-[13px] leading-relaxed whitespace-pre-wrap"
              style={{ color: 'var(--text-primary)' }}
            >
              {draftResponse}
            </p>

            {canInteract && (
              <div className="flex items-center gap-2 pt-3 mt-3" style={{ borderTop: '1px solid var(--border-hairline)' }}>
                {onApprove && (
                  <button
                    id="btn-approve-draft"
                    onClick={onApprove}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 text-[13px] font-medium"
                    style={{
                      backgroundColor: 'var(--accent)',
                      color: 'var(--on-accent)',
                      borderRadius: 'var(--radius)',
                    }}
                  >
                    <Icon name="check" size={14} />
                    Approve and send
                  </button>
                )}
                {onEdit && (
                  <button
                    id="btn-edit-draft"
                    onClick={() => setIsEditing(true)}
                    className="px-3.5 py-1.5 text-[13px] font-medium"
                    style={secondaryButton}
                  >
                    Edit
                  </button>
                )}
                {onReject && (
                  <button
                    id="btn-reject-draft"
                    onClick={onReject}
                    className="px-3.5 py-1.5 text-[13px] font-medium ml-auto"
                    style={{
                      border: '1px solid var(--status-low)',
                      borderRadius: 'var(--radius)',
                      color: 'var(--status-low)',
                      backgroundColor: 'transparent',
                    }}
                  >
                    Reject and escalate
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
};
