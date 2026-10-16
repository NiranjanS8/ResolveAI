import React, { useState, useEffect } from 'react';
import { type TicketCreate, type Channel } from '../api/tickets';
import { Icon } from './Icon';

interface TicketFormProps {
  onSubmit: (ticket: TicketCreate) => Promise<void> | void;
  onCancel?: () => void;
  isOpenAsModal?: boolean;
}

const PRESETS: Array<{ label: string; customer_id: string; channel: Channel; subject: string; body: string }> = [
  {
    label: '₹850 Refund (Within ₹2k Cap)',
    customer_id: 'cust_priya_88',
    channel: 'chat',
    subject: 'Damaged item received in order #BLR-4421',
    body: 'One of the items in my order was damaged upon arrival. I request a refund of ₹850 to my UPI account.',
  },
  {
    label: '₹3,200 Refund (> ₹2k Guardrail)',
    customer_id: 'cust_amit_corp',
    channel: 'email',
    subject: 'Invoice dispute & refund request for ₹3,200',
    body: 'We were billed ₹3,200 for extra cloud licenses that were never activated. Please issue a direct credit refund immediately.',
  },
  {
    label: '2FA Locked Out (Allow-listed Action)',
    customer_id: 'cust_rajesh_it',
    channel: 'chat',
    subject: 'Cannot login: lost access to authenticator app',
    body: 'I switched to a new phone and my 2FA app did not transfer tokens. Need emergency access reset.',
  },
  {
    label: 'Order Tracking Query (High Confidence)',
    customer_id: 'cust_sneha_k',
    channel: 'email',
    subject: 'Status of consignment #MUM-7729',
    body: 'Hello support, could you check the courier dispatch status for consignment #MUM-7729? Expected delivery was yesterday.',
  },
  {
    label: 'Urgent Outage (Critical Escalation)',
    customer_id: 'cust_enterprise_lead',
    channel: 'chat',
    subject: 'URGENT: API webhook gateway throwing 500 errors',
    body: 'Our checkout service is failing because your webhook endpoint is dropping connections. Affecting all active customers!',
  },
];

export const TicketForm: React.FC<TicketFormProps> = ({
  onSubmit,
  onCancel,
  isOpenAsModal = false,
}) => {
  const [formData, setFormData] = useState<TicketCreate>({
    customer_id: 'cust_test_user',
    channel: 'chat',
    subject: '',
    body: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpenAsModal) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpenAsModal, onCancel]);

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setFormData({
      customer_id: preset.customer_id,
      channel: preset.channel,
      subject: preset.subject,
      body: preset.body,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.customer_id.trim() || !formData.subject.trim() || !formData.body.trim()) {
      setError('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(formData);
      setFormData({
        customer_id: 'cust_test_user',
        channel: 'chat',
        subject: '',
        body: '',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ingest ticket');
    } finally {
      setSubmitting(false);
    }
  };

  const formContent = (
    <div
      className="p-5 bg-[var(--bg-surface)] border border-[var(--border-hairline)] rounded-[4px] space-y-4"
    >
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-hairline)]">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Ingest Support Ticket (Multi-Channel)
          </h2>
          <p className="text-xs text-[var(--text-secondary)]">
            Simulate or submit raw customer message across Chat or Email channels.
          </p>
        </div>
        {onCancel && (
          <button
            onClick={onCancel}
            aria-label="Close ticket form"
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <Icon name="close" size={15} />
          </button>
        )}
      </div>

      {/* Test Scenarios Quick-Pick */}
      <div>
        <label className="block text-[0.6875rem] font-semibold text-[var(--text-secondary)] uppercase mb-1.5">
          Load Pre-configured Test Scenario:
        </label>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => applyPreset(p)}
              className="text-xs px-2.5 py-1 rounded border border-[var(--border-hairline)] bg-[var(--bg-base)] text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--bg-surface-hover)] transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Customer ID *
            </label>
            <input
              id="ticket-form-cust-id"
              type="text"
              required
              value={formData.customer_id}
              onChange={(e) => setFormData({ ...formData, customer_id: e.target.value })}
              className="w-full px-3 py-1.5 text-xs rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] font-mono"
              placeholder="e.g. cust_priya_m"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
              Channel *
            </label>
            <select
              id="ticket-form-channel"
              value={formData.channel}
              onChange={(e) => setFormData({ ...formData, channel: e.target.value as Channel })}
              className="w-full px-3 py-1.5 text-xs rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
            >
              <option value="chat">Chat (WebSocket / Live chat)</option>
              <option value="email">Email (IMAP / Threaded email)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
            Subject *
          </label>
          <input
            id="ticket-form-subject"
            type="text"
            required
            value={formData.subject}
            onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
            className="w-full px-3 py-1.5 text-xs rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
            placeholder="Brief subject summary"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
            Message Body *
          </label>
          <textarea
            id="ticket-form-body"
            required
            rows={4}
            value={formData.body}
            onChange={(e) => setFormData({ ...formData, body: e.target.value })}
            className="w-full p-2.5 text-xs rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] leading-relaxed"
            placeholder="Customer issue description or incoming email body..."
          />
        </div>

        {error && (
          <div className="p-2 text-xs rounded bg-[var(--status-low-bg)] text-[var(--status-low)] border border-[var(--status-low)]">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-1.5 text-xs rounded border border-[var(--border-hairline)] text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)]"
            >
              Cancel
            </button>
          )}
          <button
            id="ticket-form-submit-btn"
            type="submit"
            disabled={submitting}
            className="px-5 py-1.5 text-xs rounded text-white font-medium transition-opacity"
            style={{
              backgroundColor: 'var(--accent)',
              opacity: submitting ? 0.6 : 1,
            }}
          >
            {submitting ? 'Running Pipeline...' : 'Ingest Ticket →'}
          </button>
        </div>
      </form>
    </div>
  );

  if (!isOpenAsModal) {
    return formContent;
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel?.();
      }}
    >
      <div
        className="w-full max-w-xl shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-label="Ingest support ticket"
      >
        {formContent}
      </div>
    </div>
  );
};