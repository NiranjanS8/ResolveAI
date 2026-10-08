import { useState, useEffect } from 'react';
import { createTicket, listTickets, type Ticket, type TicketCreate } from './api/tickets';

function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<TicketCreate>({
    customer_id: '',
    subject: '',
    body: '',
  });

  const fetchTickets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTickets();
      setTickets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tickets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const newTicket = await createTicket(formData);
      setTickets([newTicket, ...tickets]);
      setFormData({ customer_id: '', subject: '', body: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create ticket');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

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

  return (
    <div className="min-h-screen bg-[var(--bg-base)]" style={{fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif"}}>
      <header className="border-b border-[var(--border-hairline)] bg-[var(--bg-surface)]">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-xl font-semibold" style={{color: "var(--text-primary)"}}>
            ResolveAI
          </h1>
          <p className="text-sm" style={{color: "var(--text-secondary)"}}>
            Ticket Ingestion — Phase 1
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4" style={{color: "var(--text-primary)"}}>
            Submit Ticket
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4" style={{fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif"}}>
            <div>
              <label htmlFor="customer_id" className="block text-sm mb-1" style={{color: "var(--text-secondary)"}}>
                Customer ID
              </label>
              <input
                id="customer_id"
                name="customer_id"
                type="text"
                value={formData.customer_id}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border rounded-[4px] bg-[var(--bg-surface)]"
                style={{
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                  fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
                }}
                placeholder="cust_123"
              />
            </div>
            <div>
              <label htmlFor="subject" className="block text-sm mb-1" style={{color: "var(--text-secondary)"}}>
                Subject
              </label>
              <input
                id="subject"
                name="subject"
                type="text"
                value={formData.subject}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border rounded-[4px] bg-[var(--bg-surface)]"
                style={{
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                  fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
                }}
                placeholder="Brief summary of the issue"
              />
            </div>
            <div>
              <label htmlFor="body" className="block text-sm mb-1" style={{color: "var(--text-secondary)"}}>
                Description
              </label>
              <textarea
                id="body"
                name="body"
                value={formData.body}
                onChange={handleChange}
                required
                rows={4}
                className="w-full px-3 py-2 border rounded-[4px] bg-[var(--bg-surface)]"
                style={{
                  borderColor: 'var(--border-hairline)',
                  color: 'var(--text-primary)',
                  fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
                }}
                placeholder="Detailed description of the issue..."
              />
            </div>
            <button
              type="submit"
              disabled={submitting || !formData.customer_id || !formData.subject || !formData.body}
              className="px-4 py-2 rounded-[4px] font-medium text-sm transition-colors"
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
              <p className="text-sm" style={{color: 'var(--status-low)'}}>
                {error}
              </p>
            )}
          </form>
        </section>

        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold" style={{color: "var(--text-primary)"}}>
              Tickets
            </h2>
            <button
              onClick={fetchTickets}
              disabled={loading}
              className="px-3 py-1 text-sm border rounded-[4px] transition-colors"
              style={{
                borderColor: 'var(--border-hairline)',
                color: 'var(--text-primary)',
                backgroundColor: 'var(--bg-surface)',
                fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
              }}
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>

          {error && !loading && (
            <p className="text-sm mb-4" style={{color: 'var(--status-low)'}}>
              {error}
            </p>
          )}

          <div className="border rounded-[4px] overflow-hidden" style={{borderColor: 'var(--border-hairline)'}}>
            <table className="w-full" style={{fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif"}}>
              <thead>
                <tr className="bg-[var(--bg-surface-hover)]" style={{borderBottom: '1px solid var(--border-hairline)'}}>
                  <th className="px-4 py-3 text-left text-sm font-medium" style={{color: "var(--text-secondary)", borderRight: '1px solid var(--border-hairline)'}>
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium" style={{color: "var(--text-secondary)", borderRight: '1px solid var(--border-hairline)'}>
                    Subject
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium" style={{color: "var(--text-secondary)", borderRight: '1px solid var(--border-hairline)'}>
                    Customer
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium" style={{color: "var(--text-secondary)"}>
                    Created
                  </th>
                </tr>
              </thead>
              <tbody>
                {tickets.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center" style={{color: "var(--text-secondary)"}}>
                      No tickets yet. Submit one above.
                    </td>
                  </tr>
                ) : (
                  tickets.map((ticket) => (
                    <tr key={ticket.id} className="border-t" style={{borderColor: 'var(--border-hairline)'}}>
                      <td className="px-4 py-3">
                        <div
                          className="flex items-center gap-2"
                          style={{
                            borderLeft: `3px solid ${statusColors[ticket.status] || 'var(--text-secondary)'}`,
                            paddingLeft: '8px',
                          }}
                        >
                          <span className="text-sm" style={{color: "var(--text-secondary)"}}>
                            {statusLabels[ticket.status] || ticket.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-medium" style={{color: "var(--text-primary)"}}>
                          {ticket.subject}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm" style={{color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', 'SF Mono', Consolas, monospace"}}>
                          {ticket.customer_id}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm" style={{color: "var(--text-secondary)", fontFamily: "'IBM Plex Mono', 'SF Mono', Consolas, monospace"}}>
                          {new Date(ticket.created_at).toLocaleString()}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;