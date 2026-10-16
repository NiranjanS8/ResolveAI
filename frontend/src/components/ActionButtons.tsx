import React, { useState } from 'react';
import { type Ticket } from '../api/tickets';

interface ActionButtonsProps {
  ticket: Ticket;
  canApprove: boolean;
  canEdit: boolean;
  canReject: boolean;
  onApprove: () => void;
  onEdit: (editedDraft: string) => void;
  onReject: () => void;
  onRefund?: (amount: number) => void;
  onOrderStatus?: () => void;
  onPasswordReset?: () => void;
}

/**
 * Secondary tool-action panel — shown below the DraftCard.
 * Primary HITL actions (Approve/Edit/Reject) live in DraftCard; this component
 * only exposes guardrailed tool calls: Refund, Order Status, Password Reset.
 */
export const ActionButtons: React.FC<ActionButtonsProps> = ({
  ticket,
  onRefund,
  onOrderStatus,
  onPasswordReset,
}) => {
  const [showRefundInput, setShowRefundInput] = useState(false);
  const [refundAmount, setRefundAmount]       = useState('850');

  const handleRefundSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(refundAmount);
    if (!isNaN(val) && val > 0 && onRefund) {
      onRefund(val);
      setShowRefundInput(false);
    }
  };

  const exceedsCap     = parseFloat(refundAmount) > 2000;
  const hasToolActions = onRefund || onOrderStatus || onPasswordReset;

  if (!hasToolActions) return null;

  return (
    <div className="space-y-2.5">
      {/* Tool actions header */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          Tool Actions
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded font-mono" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
          guardrailed
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {onRefund && (
          <button
            id="action-btn-refund-toggle"
            onClick={() => setShowRefundInput(!showRefundInput)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
            style={{
              backgroundColor: showRefundInput ? 'var(--yellow-dim)' : 'var(--bg-elevated)',
              color: showRefundInput ? 'var(--yellow)' : 'var(--text-secondary)',
              border: `1px solid ${showRefundInput ? 'rgba(210,153,34,.3)' : 'var(--border)'}`,
            }}
          >
            ₹ Issue Refund
          </button>
        )}

        {onOrderStatus && (
          <button
            id="action-btn-order-status"
            onClick={onOrderStatus}
            className="px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            Track Order
          </button>
        )}

        {onPasswordReset && (
          <button
            id="action-btn-pwd-reset"
            onClick={onPasswordReset}
            className="px-3 py-1.5 text-xs rounded-md font-medium transition-colors"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            Reset 2FA / Pass
          </button>
        )}
      </div>

      {/* Refund guardrail drawer */}
      {showRefundInput && (
        <form
          onSubmit={handleRefundSubmit}
          className="p-3.5 rounded-lg space-y-2.5 animate-slide-in"
          style={{
            backgroundColor: 'var(--bg-elevated)',
            border: `1px solid ${exceedsCap ? 'rgba(248,81,73,.3)' : 'var(--border)'}`,
          }}
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
              Guardrailed Refund (INR)
            </span>
            <span
              className="px-2 py-0.5 rounded-full font-medium font-mono"
              style={{
                backgroundColor: exceedsCap ? 'var(--red-dim)'    : 'var(--green-dim)',
                color:           exceedsCap ? 'var(--red)'        : 'var(--green)',
              }}
            >
              {exceedsCap ? '⚠ Exceeds ₹2,000 cap — requires supervisor' : '✓ Within ₹2,000 auto-cap'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <span
                className="absolute left-3 top-1/2 -translate-y-1/2 text-sm"
                style={{ color: 'var(--text-secondary)' }}
              >
                ₹
              </span>
              <input
                id="input-refund-amount"
                type="number"
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="w-full pl-6 pr-3 py-2 text-sm rounded-md"
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: `1px solid ${exceedsCap ? 'var(--red)' : 'var(--border)'}`,
                  color: 'var(--text-primary)',
                }}
                placeholder="Amount in INR"
                required
              />
            </div>
            <button
              id="btn-process-refund"
              type="submit"
              className="px-4 py-2 text-sm font-medium rounded-md text-white"
              style={{ backgroundColor: exceedsCap ? 'var(--yellow)' : 'var(--accent)' }}
            >
              Execute
            </button>
          </div>
        </form>
      )}
    </div>
  );
};