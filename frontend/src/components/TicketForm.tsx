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
    label: '₹850 refund, within cap',
    customer_id: 'cust_priya_88',
    channel: 'chat',
    subject: 'Damaged item received in order #BLR-4421',
    body: 'One of the items in my order was damaged upon arrival. I request a refund of ₹850 to my UPI account.',
  },
  {
    label: '₹3,200 refund, over cap',
    customer_id: 'cust_amit_corp',
    channel: 'email',
    subject: 'Invoice dispute and refund request for ₹3,200',
    body: 'We were billed ₹3,200 for extra cloud licenses that were never activated. Please issue a direct credit refund immediately.',
  },
  {
    label: 'Order tracking query',
    customer_id: 'cust_sneha_k',
    channel: 'email',
    subject: 'Status of consignment #MUM-7729',
    body: 'Hello support, could you check the courier dispatch status for consignment #MUM-7729? Expected delivery was yesterday.',
  },
  {
    label: 'Urgent API outage',
    customer_id: 'cust_enterprise_lead',
    channel: 'chat',
    subject: 'URGENT: API webhook gateway throwing 500 errors',
    body: 'Our checkout service is failing because your webhook endpoint is dropping connections. Affecting all active customers!',
  },
];

const fieldStyle: React.CSSProperties = {
  width: '100%',
  padding: '6px 12px',
  fontSize: 13,
  backgroundColor: 'var(--bg-surface)',
  border: '1px solid var(--border-hairline)',
  borderRadius: 'var(--radius)',
  color: 'var(--text-primary)',
};

export const TicketForm: React.FC<TicketFormProps> = ({
  onSubmit,
  onCancel,
  isOpenAsModal = false,
}) => {
  const [formData, setFormData] = useState<TicketCreate>({
    customer_id: '',
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

  const applyPreset = (preset: (typeof PRESETS)[0]) => {
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
      setError('Customer ID, subject and body are all required.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(formData);
      setFormData({ customer_id: '', channel: 'chat', subject: '', body: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ingest ticket');
    } finally {
      setSubmitting(false);
    }
  };

  const formContent = (
    <div
      className="p-5 space-y-4"
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderRadius: 'var(--radius)',
      }}
    >
      <div
        className="flex items-start justify-between gap-3 pb-3"
        style={{ borderBottom: '1px solid var(--border-hairline)' }}
      >
        <div>
          <h2 className="text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>
            Ingest support ticket
          </h2>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Submit a raw customer message from chat or email.
          </p>
        </div>
        {onCancel && (
          <button onClick={onCancel} aria-label="Close ticket form" style={{ color: 'var(--text-secondary)' }}>
            <Icon name="close" size={15} />
          </button>
        )}
      </div>

      <div>
        <label className="block text-[12px] font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>
          Load a test scenario
        </label>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => applyPreset(preset)}
              className="text-[12px] px-2.5 py-1"
              style={{
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--radius)',
                color: 'var(--text-primary)',
                backgroundColor: 'transparent',
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="ticket-form-cust-id" className="block text-[12px] font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
              Customer ID
            </label>
            <input
              id="ticket-form-cust-id"
              type="text"
              required
              value={formData.customer_id}
              onChange={(e) => setFormData({ ...formData, customer_id: e.target.value })}
              className="font-mono"
              style={fieldStyle}
              placeholder="cust_priya_m"
            />
          </div>

          <div>
            <label htmlFor="ticket-form-channel" className="block text-[12px] font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
              Channel
            </label>
            <select
              id="ticket-form-channel"
              value={formData.channel}
              onChange={(e) => setFormData({ ...formData, channel: e.target.value as Channel })}
              style={fieldStyle}
            >
              <option value="chat">Chat</option>
              <option value="email">Email</option>
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="ticket-form-subject" className="block text-[12px] font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
            Subject
          </label>
          <input
            id="ticket-form-subject"
            type="text"
            required
            value={formData.subject}
            onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
            style={fieldStyle}
            placeholder="Brief subject summary"
          />
        </div>

        <div>
          <label htmlFor="ticket-form-body" className="block text-[12px] font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
            Message body
          </label>
          <textarea
            id="ticket-form-body"
            required
            rows={4}
            value={formData.body}
            onChange={(e) => setFormData({ ...formData, body: e.target.value })}
            style={{ ...fieldStyle, padding: '10px 12px', lineHeight: 1.6 }}
            placeholder="Customer issue description or inbound email body"
          />
        </div>

        {error && (
          <p className="text-[12px] flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
            <Icon name="alert" size={13} />
            {error}
          </p>
        )}

        <div className="flex items-center justify-end gap-2 pt-1">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3.5 py-1.5 text-[13px] font-medium"
              style={{
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--radius)',
                color: 'var(--text-secondary)',
                backgroundColor: 'transparent',
              }}
            >
              Cancel
            </button>
          )}
          <button
            id="ticket-form-submit-btn"
            type="submit"
            disabled={submitting}
            className="px-3.5 py-1.5 text-[13px] font-medium"
            style={{
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--radius)',
              color: 'var(--text-primary)',
              backgroundColor: 'transparent',
              opacity: submitting ? 0.6 : 1,
              cursor: submitting ? 'progress' : 'pointer',
            }}
          >
            {submitting ? 'Running pipeline' : 'Ingest ticket'}
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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      style={{ backgroundColor: 'var(--scrim)' }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel?.();
      }}
    >
      <div className="w-full max-w-xl" role="dialog" aria-modal="true" aria-label="Ingest support ticket">
        {formContent}
      </div>
    </div>
  );
};
