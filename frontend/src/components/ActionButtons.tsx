import React, { useState } from 'react';
import { type Ticket } from '../api/tickets';
import { Icon } from './Icon';
import { REFUND_INR_CAP, intentLabel } from '../lib/ticketDisplay';

interface ActionButtonsProps {
  ticket: Ticket;
  onRefund?: (amount: number) => void;
  onOrderStatus?: () => void;
  onPasswordReset?: () => void;
}

type ToolId = 'refund' | 'order_status' | 'password_reset';

/* A tool is only offered where its intent makes it meaningful. Anything else is
   shown disabled with the reason, rather than firing on an unrelated ticket. */
const APPLICABLE_INTENTS: Record<ToolId, string[]> = {
  refund: ['refund', 'billing', 'cancellation'],
  order_status: ['order_status', 'refund', 'billing', 'cancellation', 'technical'],
  password_reset: ['password_reset', 'account', 'technical'],
};

const TOOLS: Array<{ id: ToolId; label: string; reason: string }> = [
  { id: 'refund', label: 'Issue refund', reason: 'Applies to refund, billing and cancellation tickets.' },
  { id: 'order_status', label: 'Track order', reason: 'Applies to order, delivery and billing tickets.' },
  { id: 'password_reset', label: 'Reset 2FA or password', reason: 'Applies to account and access tickets.' },
];

const isApplicable = (tool: ToolId, ticket: Ticket) => {
  const intent = ticket.intent ?? 'general';
  return APPLICABLE_INTENTS[tool].includes(intent);
};

export const ActionButtons: React.FC<ActionButtonsProps> = ({
  ticket,
  onRefund,
  onOrderStatus,
  onPasswordReset,
}) => {
  const [showRefundInput, setShowRefundInput] = useState(false);
  const [refundAmount, setRefundAmount] = useState('850');

  const handlers: Record<ToolId, (() => void) | undefined> = {
    refund: onRefund ? () => setShowRefundInput((open) => !open) : undefined,
    order_status: onOrderStatus,
    password_reset: onPasswordReset,
  };

  const handleRefundSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = Number.parseFloat(refundAmount);
    if (Number.isFinite(amount) && amount > 0 && onRefund) {
      onRefund(amount);
      setShowRefundInput(false);
    }
  };

  const exceedsCap = Number.parseFloat(refundAmount) > REFUND_INR_CAP;

  return (
    <section aria-label="Tool actions" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] mr-1" style={{ color: 'var(--text-secondary)' }}>
          Tools
        </span>
        {TOOLS.map((tool) => {
          const applicable = isApplicable(tool.id, ticket);
          const handler = handlers[tool.id];
          const available = applicable && Boolean(handler);
          return (
            <button
              key={tool.id}
              id={`action-btn-${tool.id}`}
              disabled={!available}
              title={available ? tool.label : `Not applicable — ${tool.reason}`}
              onClick={handler}
              className="px-3 py-1.5 text-[13px] font-medium whitespace-nowrap"
              style={{
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--radius)',
                backgroundColor: 'transparent',
                color: available ? 'var(--text-primary)' : 'var(--text-secondary)',
                opacity: available ? 1 : 0.6,
                cursor: available ? 'pointer' : 'not-allowed',
              }}
            >
              {tool.label}
            </button>
          );
        })}
      </div>

      {!TOOLS.some((tool) => isApplicable(tool.id, ticket)) && (
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          No tool applies to a {intentLabel(ticket.intent)?.toLowerCase() ?? 'general'} ticket — it needs a human.
        </p>
      )}

      {showRefundInput && isApplicable('refund', ticket) && (
        <form
          onSubmit={handleRefundSubmit}
          className="p-3.5 space-y-2.5 animate-slide-in"
          style={{ border: '1px solid var(--border-hairline)' }}
        >
          <div className="flex items-center justify-between gap-2 text-[12px]">
            <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
              Refund (INR)
            </span>
            <span className="inline-flex items-center gap-1.5" style={{ color: 'var(--text-secondary)' }}>
              <Icon name={exceedsCap ? 'alert' : 'shield'} size={12} />
              {exceedsCap
                ? `Over the ₹${REFUND_INR_CAP.toLocaleString('en-IN')} cap — routes to human review`
                : `Within the ₹${REFUND_INR_CAP.toLocaleString('en-IN')} auto-cap`}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <span
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[13px] font-mono"
                style={{ color: 'var(--text-secondary)' }}
              >
                ₹
              </span>
              <input
                id="input-refund-amount"
                type="number"
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="w-full pl-6 pr-3 py-1.5 text-[13px] font-mono"
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-hairline)',
                  borderRadius: 'var(--radius)',
                  color: 'var(--text-primary)',
                }}
                placeholder="Amount in INR"
                required
              />
            </div>
            <button
              id="btn-process-refund"
              type="submit"
              className="px-3.5 py-1.5 text-[13px] font-medium"
              style={{
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--radius)',
                color: 'var(--text-primary)',
                backgroundColor: 'transparent',
              }}
            >
              Execute
            </button>
          </div>
        </form>
      )}
    </section>
  );
};
