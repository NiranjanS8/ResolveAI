import React, { useState } from 'react';
import './index.css';

/**
 * Phase 1: Ticket submission form
 * Per design.md: dense form, hairline borders (1px), no card shadows,
 * no ALL-CAPS labels, no tracked-out eyebrow text
 */
interface TicketFormProps {
  onSubmit: (ticket: {
    customer_id: string;
    subject: string;
    body: string;
    channel: string;
  }) => void;
  initialValues?: {
    customer_id?: string;
    subject?: string;
    body?: string;
    channel?: string;
  };
}

export const TicketForm: React.FC<TicketFormProps> = ({
  onSubmit,
  initialValues = {
    customer_id: '',
    subject: '',
    body: '',
    channel: 'chat',
  },
}) => {
  const [formData, setFormData] = useState(initialValues);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      onSubmit(formData);
      setFormData({
        customer_id: '',
        subject: '',
        body: '',
        channel: 'chat',
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create ticket'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="mb-8">
      <h2 className="text-lg font-medium mb-4" style={{ color: 'var(--text-primary)' }}>
        Submit Ticket
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4" style={{ fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif" }}>
        <div>
          <label htmlFor="customer_id" className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
            Customer ID
          </label>
          <input
            id="customer_id"
            name="customer_id"
            type="text"
            value={formData.customer_id}
            onChange={handleChange}
            required
            className="w-full px-3 py-2 border border-[var(--border-hairline)] bg-[var(--bg-surface)] rounded-[4px]"
            style={{
              color: 'var(--text-primary)',
              fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            }}
            placeholder="cust_123"
          />
        </div>

        <div>
          <label htmlFor="subject" className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
            Subject
          </label>
          <input
            id="subject"
            name="subject"
            type="text"
            value={formData.subject}
            onChange={handleChange}
            required
            className="w-full px-3 py-2 border border-[var(--border-hairline)] bg-[var(--bg-surface)] rounded-[4px]"
            style={{
              color: 'var(--text-primary)',
              fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            }}
            placeholder="Brief summary of the issue"
          />
        </div>

        <div>
          <label htmlFor="body" className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
            Description
          </label>
          <textarea
            id="body"
            name="body"
            value={formData.body}
            onChange={handleChange}
            required
            rows={4}
            className="w-full px-3 py-2 border border-[var(--border-hairline)] bg-[var(--bg-surface)] rounded-[4px]"
            style={{
              color: 'var(--text-primary)',
              fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            }}
            placeholder="Detailed description of the issue..."
          ></textarea>
        </div>

        <div>
          <label htmlFor="channel" className="block text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
            Channel
          </label>
          <select
            id="channel"
            name="channel"
            value={formData.channel}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-[var(--border-hairline)] bg-[var(--bg-surface)] rounded-[4px]"
            style={{
              color: 'var(--text-primary)',
              fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            }}
          >
            <option value="chat">Chat</option>
            <option value="email">Email</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full px-4 py-2 rounded-[4px] font-medium text-sm transition-colors"
          style={{
            backgroundColor: 'var(--accent)',
            color: 'white',
            fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            opacity: submitting || !formData.customer_id || !formData.subject || !formData.body ? 0.6 : 1,
          }}
        >
          {submitting ? 'Submitting...' : 'Create Ticket'}
        </button>
        {error && (
          <p className="text-sm" style={{ color: 'var(--status-low)' }}>
            {error}
          </p>
        )}
      </form>
    </div>
  );
}