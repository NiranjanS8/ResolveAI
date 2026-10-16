import React, { useState } from 'react';
import { Icon } from './Icon';

interface DraftCardProps {
  draftResponse: string | null | undefined;
  intent: string | null | undefined;
  confidence?: number | null;
  onApprove?: () => void;
  onEdit?: (edited: string) => void;
  onReject?: () => void;
  canInteract?: boolean;
}

export const DraftCard: React.FC<DraftCardProps> = ({
  draftResponse,
  intent,
  confidence,
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

  return (
    <div
      className="rounded-lg animate-slide-in"
      style={{
        backgroundColor: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderLeft: '3px solid var(--accent)',
      }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <span
            className="flex items-center gap-1.5 text-xs font-mono font-semibold uppercase tracking-wider"
            style={{ color: 'var(--accent)' }}
          >
            <Icon name="sparkle" size={13} />
            AI Draft Response
          </span>
          {intent && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-mono"
              style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-muted)' }}
            >
              intent: {intent}
            </span>
          )}
        </div>
        {confidence != null && (
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            {Math.round(confidence * 100)}% match
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={5}
              className="w-full p-3 text-sm rounded-md leading-relaxed"
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--accent)',
                color: 'var(--text-primary)',
                resize: 'vertical',
              }}
              placeholder="Edit draft response before sending…"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={handleCancelEdit}
                className="px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
                style={{
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                  backgroundColor: 'transparent',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-1.5 text-xs rounded-md font-medium text-white"
                style={{ backgroundColor: 'var(--accent)' }}
              >
                Save & Dispatch
              </button>
            </div>
          </div>
        ) : (
          <>
            <p
              className="text-sm leading-relaxed whitespace-pre-wrap mb-4"
              style={{ color: 'var(--text-primary)' }}
            >
              {draftResponse}
            </p>

            {canInteract && (
              <div
                className="flex items-center gap-2 pt-3"
                style={{ borderTop: '1px solid var(--border)' }}
              >
                {onApprove && (
                  <button
                    id="btn-approve-draft"
                    onClick={onApprove}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 text-sm rounded-md font-medium text-white transition-opacity hover:opacity-90"
                    style={{ backgroundColor: 'var(--green)' }}
                  >
                    <Icon name="check" size={14} /> Approve & Send
                  </button>
                )}
                {onEdit && (
                  <button
                    id="btn-edit-draft"
                    onClick={() => setIsEditing(true)}
                    className="px-3.5 py-1.5 text-sm rounded-md font-medium transition-colors"
                    style={{
                      border: '1px solid var(--border)',
                      color: 'var(--text-primary)',
                      backgroundColor: 'transparent',
                    }}
                  >
                    Edit Draft
                  </button>
                )}
                {onReject && (
                  <button
                    id="btn-reject-draft"
                    onClick={onReject}
                    className="px-3.5 py-1.5 text-sm rounded-md font-medium transition-colors ml-auto"
                    style={{
                      border: '1px solid var(--red)',
                      color: 'var(--red)',
                      backgroundColor: 'transparent',
                    }}
                  >
                    Reject & Escalate
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};