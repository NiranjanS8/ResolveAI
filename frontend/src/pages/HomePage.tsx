import React, { useState, useEffect } from 'react';
import './index.css';
import { TicketForm } from '../components/TicketForm';
import { TicketList } from '../components/TicketList';
import { ActionButtons } from '../components/ActionButtons';
import { DraftCard } from '../components/DraftCard';
import { AnalyticsChart } from '../components/AnalyticsChart';

/**
 * Phase 1-10: Main dashboard/home page
 * Combines ticket form, list, detail view, and analytics.
 * Ties together all 10 phases of the ResolveAI build.
 */
interface HomePageProps {
  /** Injected by parent via state management */
  tickets?: any[];
  onDetail?: (ticket: any) => void;
  onApprove?: (ticket: any) => void;
  onEdit?: (ticket: any) => void;
  onReject?: (ticket: any) => void;
}

export const HomePage: React.FC<HomePageProps> = ({
  tickets,
  onDetail,
  onApprove,
  onEdit,
  onReject,
}) => {
  const [selectedTicket, setSelectedTicket] = useState<any | null>(null);
  const [showDraft, setShowDraft] = useState(false);
  const [draftResponse, setDraftResponse] = useState<string | null>(null);
  const [filterChannel, setFilterChannel] = useState<'all' | 'email' | 'chat'>('all');
  const [canEdit, setCanEdit] = useState(false);

  // Filter tickets by channel
  const filteredTickets = tickets
    ? tickets.filter(
        t => filterChannel === 'all' || t.channel === filterChannel
      )
    : [];

  // Handle detail view selection
  const handleDetail = (ticket: any) => {
    setSelectedTicket(ticket);
    setShowDraft(!!ticket.draft_response);
    setDraftResponse(ticket.draft_response || '');
  };

  // Handle approve
  const handleApprove = () => {
    onApprove?.(selectedTicket!);
    setShowDraft(false);
    setDraftResponse('');
    setSelectedTicket(null);
  };

  // Handle edit
  const handleEdit = () => {
    if (draftResponse) {
      onEdit(draftResponse);
      setShowDraft(false);
      setDraftResponse('');
      setSelectedTicket(null);
    }
  };

  // Handle reject
  const handleReject = () => {
    onReject?.(selectedTicket!);
    setShowDraft(false);
    setDraftResponse('');
    setSelectedTicket(null);
  };

  return (
    <div className="min-h-screen bg-[var(--bg-base)] pb-8">
      {/* Header */}
      <header className="border-b border-[var(--border-hairline)] bg-[var(--bg-surface)]">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            ResolveAI
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Ticket Ingestion — Phase 1 • Multi-Channel Support
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Phase 1: Ticket Submission Form */}
        <section className="mb-6">
          <TicketForm onSubmit={({ customer_id, subject, body, channel }) => {
            // Create ticket via API would go here
            // For now, add to local state
            const newTicket = {
              id: Date.now().toString(),
              customer_id,
              subject,
              body,
              status: 'new',
              channel,
              draft_response: undefined,
            };
            // Simulate creation
            setTimeout(() => {
              onDetail?.(newTicket);
            }, 100);
          }}>
          {/* If in detail view, hide the form or show it conditionally */}
          {selectedTicket === null && (
            <TicketForm
              onSubmit={({ customer_id, subject, body, channel }) => {
                const newTicket = {
                  id: Date.now().toString(),
                  customer_id,
                  subject,
                  body,
                  channel,
                  status: 'new',
                  draft_response: undefined,
                };
                onDetail?.(newTicket);
              }}
            />
          )}
        </section>

        {/* Phase 6: Agent Dashboard Queue */}
        <section>
          <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
            Ticket Queue {filterChannel !== 'all' ? `(${filterChannel})` : ''}
            <button
              onClick={() => setFilterChannel(c => c === 'all' ? 'email' : c === 'email' ? 'chat' : 'all')}
              style={{
                marginLeft: '8px',
                background: 'none',
                border: 'none',
                color: 'var(--accent)',
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}
            >
              {filterChannel}
            </button>
          </h2>
          <TicketList
            tickets={filteredTickets}
            onDetail={handleDetail}
            onApprove={selectedTicket?.draft_response && handleApprove}
            onEdit={selectedTicket?.draft_response && handleEdit}
            onReject={handleReject}
            canEdit={!!selectedTicket?.draft_response}
          />
        </section>

        {/* Phase 5-6: Detail View & Draft Card */}
        {selectedTicket && (
          <section className="mt-6">
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
              Ticket Detail
            </h2>

            <div className="bg-[var(--bg-surface)] rounded-[4px] p-4 mb-4" style={{
              border: '1px solid var(--border-hairline)',
              fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
            }}>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Customer ID:</strong> {selectedTicket.customer_id}
              </p>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Subject:</strong> {selectedTicket.subject}
              </p>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Intent:</strong> {selectedTicket.intent || '—'}
              </p>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Urgency:</strong> {selectedTicket.urgency || '—'}
              </p>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Sentiment:</strong> {selectedTicket.sentiment || '—'}
              </p>
              <p className="text-[var(--text-secondary)] text-sm mb-2">
                <strong>Confidence:</strong> {selectedTicket.confidence || '—'}
              </p>
            </div>

            <DraftCard
              draftResponse={selectedTicket.draft_response}
              intent={selectedTicket.intent}
              canInteract={!!selectedTicket}
              onApprove={handleApprove}
              onEdit={(edited) => {
                setDraftResponse(edited);
              }}
              onReject={handleReject}
            />

            {/* Phase 7: Action Buttons for allowed actions */}
            {selectedTicket && (
              <ActionButtons
                ticket={selectedTicket}
                canApprove={!!selectedTicket.draft_response}
                canEdit={!!selectedTicket.draft_response}
                canReject={!!selectedTicket.draft_response}
                onApprove={handleApprove}
                onEdit={(edited) => setDraftResponse(edited)}
                onReject={handleReject}
              />
            )}
          </section>
        )}

        {/* Phase 9: Analytics Section */}
        {selectedTicket === null && (
          <section className="mt-6">
            <h2 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
              Analytics
            </h2>
            <AnalyticsChart
              title="Deflection Rate"
              data={[]}
              metric="deflection_rate"
              range="30d"
            />
            <AnalyticsChart
              title="Cost per Ticket"
              data={[]}
              metric="cost_per_ticket"
              range="30d"
            />
            <AnalyticsChart
              title="Escalation Reasons"
              data={[]}
              metric="escalation_breakdown"
              range="30d"
            />
          </section>
        )}

        {/* Phase 10: Channel Filter */}
        <section className="mt-6 pt-6 border-t border-[var(--border-hairline)]">
          <p className="text-[var(--text-secondary)] text-sm mb-4">
            Channel:
            <button
              onClick={() => setFilterChannel('all')}
              style={{ marginRight: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              All
            </button>
            <button
              onClick={() => setFilterChannel('chat')}
              style={{ marginRight: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Chat
            </button>
            <button
              onClick={() => setFilterChannel('email')}
              style={{ marginRight: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Email
            </button>
          </p>
        </section>
      </main>
    </div>
  );
}