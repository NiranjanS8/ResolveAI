import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  type Ticket,
  type TicketCreate,
  type Channel,
  listTickets,
  createTicket,
  getTicket,
  approveDraft,
  editDraft,
  rejectDraft,
  processRefundAction,
  processOrderStatusAction,
  processPasswordResetAction,
  addMessage,
  errorMessage,
} from '../api/tickets';
import { Navbar } from '../components/Navbar';
import { TicketList } from '../components/TicketList';
import { TicketDetailPane } from '../components/TicketDetailPane';
import { TicketForm } from '../components/TicketForm';
import { AnalyticsDashboardView } from '../components/AnalyticsDashboardView';
import { ToastContainer, type ToastMessage } from '../components/Toast';
import { Icon } from '../components/Icon';

interface StatProps {
  label: string;
  value: string | number;
}

const Stat: React.FC<StatProps> = ({ label, value }) => (
  <span className="flex items-baseline gap-1.5">
    <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
    <span className="font-mono font-semibold" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
  </span>
);

export const HomePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'queue' | 'analytics'>('queue');
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [filterChannel, setFilterChannel] = useState<'all' | Channel>('all');
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  /* Which ticket stays open, readable from the poller without making the poller
     depend on `selectedTicket`. That dependency was the switching bug: `loadData`
     wrote `selectedTicket`, which changed `loadData`'s identity, which restarted
     the effect that calls `loadData` — so the page polled in a loop, and racing
     responses repainted the pane with whichever ticket answered last.
     `undefined` = nothing chosen yet, `null` = the user closed the pane. */
  const selectedIdRef = useRef<string | null | undefined>(undefined);
  // Monotonic token: a detail response older than the current one is dropped.
  const detailRequestRef = useRef(0);

  const addToast = (type: ToastMessage['type'], message: string) => {
    const id = `toast_${Date.now()}_${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  /** Load the full record for a ticket — its messages, audit log and retrieved
      sources — which the list endpoint omits. The result is applied only if the
      same ticket is still selected and no newer request has overtaken it, so a
      slow response can never put one customer's conversation under another
      customer's header. */
  const refreshDetail = useCallback(async (ticketId: string, silent = false) => {
    const requestId = ++detailRequestRef.current;
    if (!silent) setDetailLoading(true);
    try {
      const detail = await getTicket(ticketId);
      if (requestId === detailRequestRef.current && ticketId === selectedIdRef.current) {
        setSelectedTicket(detail);
        setDetailError(null);
      }
    } catch (error) {
      // Keep the summary in the header, but never present its empty detail
      // sections — conversation, sources, audit — as if they were empty facts.
      if (requestId === detailRequestRef.current && ticketId === selectedIdRef.current) {
        setDetailError(errorMessage(error));
      }
    } finally {
      if (requestId === detailRequestRef.current) setDetailLoading(false);
    }
  }, []);

  /** Open a ticket from the queue: swap the pane to it immediately, then fill
      in the detail. Showing the summary at once means the panel never lingers
      on the ticket the agent just clicked away from. */
  const handleSelectTicket = useCallback(
    (ticket: Ticket) => {
      selectedIdRef.current = ticket.id;
      setSelectedTicket(ticket);
      setDetailError(null);
      void refreshDetail(ticket.id);
    },
    [refreshDetail],
  );

  const handleCloseDetail = useCallback(() => {
    selectedIdRef.current = null;
    detailRequestRef.current += 1; // abandon any detail still in flight
    setSelectedTicket(null);
    setDetailLoading(false);
    setDetailError(null);
  }, []);

  const loadData = useCallback(async () => {
    try {
      const data = await listTickets();
      setTickets(data);
      // Connectivity reflects the call that supplies the data, not a separate
      // probe, so the indicator can never read "Live" over a stale or failed list.
      setIsBackendConnected(true);
      setLoadError(null);

      const current = selectedIdRef.current;
      const target =
        current === null
          ? null // the pane was closed on purpose; leave it closed
          : current === undefined
            ? data[0] ?? null // first load: open the newest ticket
            : data.find((t) => t.id === current) ?? data[0] ?? null;

      if (!target) {
        selectedIdRef.current = null;
        setSelectedTicket(null);
        return;
      }

      // Only touch the pane when the queue says the selection changed; otherwise
      // refresh the detail behind the agent's back instead of flashing a loader.
      const changed = target.id !== selectedIdRef.current;
      selectedIdRef.current = target.id;
      if (changed) setSelectedTicket(target);
      await refreshDetail(target.id, !changed);
    } catch (error) {
      setIsBackendConnected(false);
      setLoadError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [refreshDetail]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleApprove = async (ticket: Ticket) => {
    try {
      const updated = await approveDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('success', `Ticket #${ticket.id.slice(0, 8)} approved. AI draft dispatched to customer.`);
    } catch (error) {
      addToast('error', `Failed to approve #${ticket.id.slice(0, 8)}: ${errorMessage(error)}`);
    }
  };

  const handleEdit = async (ticket: Ticket, editedDraft: string) => {
    try {
      const updated = await editDraft(ticket.id, editedDraft);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('success', `Edited response for #${ticket.id.slice(0, 8)} sent successfully.`);
    } catch (error) {
      addToast('error', `Failed to send edited draft for #${ticket.id.slice(0, 8)}: ${errorMessage(error)}`);
    }
  };

  const handleReject = async (ticket: Ticket) => {
    try {
      const updated = await rejectDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('warning', `Ticket #${ticket.id.slice(0, 8)} draft rejected. Routed to a human.`);
    } catch (error) {
      addToast('error', `Failed to reject #${ticket.id.slice(0, 8)}: ${errorMessage(error)}`);
    }
  };

  const handleRefund = async (ticket: Ticket, amount: number) => {
    try {
      const updated = await processRefundAction(ticket.id, amount);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      if (amount > 2000) {
        addToast('warning', `Refund of ₹${amount} exceeds the ₹2,000 cap. Supervisor approval required.`);
      } else {
        addToast('success', `Refund of ₹${amount} processed under the ₹2,000 auto-cap.`);
      }
    } catch (error) {
      addToast('error', `Refund execution failed for #${ticket.id.slice(0, 8)}: ${errorMessage(error)}`);
    }
  };

  const handleOrderStatus = async (ticket: Ticket) => {
    try {
      const updated = await processOrderStatusAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('info', `Order status lookup executed for #${ticket.id.slice(0, 8)}.`);
    } catch (error) {
      addToast('error', `Order status lookup failed: ${errorMessage(error)}`);
    }
  };

  const handlePasswordReset = async (ticket: Ticket) => {
    try {
      const updated = await processPasswordResetAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('success', `Secure password reset link dispatched to ${ticket.customer_id}`);
    } catch (error) {
      addToast('error', `Password reset failed: ${errorMessage(error)}`);
    }
  };

  const handleSendMessage = async (ticket: Ticket, text: string) => {
    try {
      const newMessage = await addMessage(ticket.id, text, 'agent');
      const updated: Ticket = { ...ticket, messages: [...(ticket.messages || []), newMessage] };
      setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
      await refreshDetail(updated.id, true);
      addToast('info', 'Message posted to the conversation.');
    } catch (error) {
      addToast('error', `Failed to send reply: ${errorMessage(error)}`);
    }
  };

  const handleCreateTicket = async (formData: TicketCreate) => {
    try {
      const created = await createTicket(formData);
      setTickets((prev) => [created, ...prev]);
      handleSelectTicket(created);
      setIsModalOpen(false);
      addToast('success', `Ticket #${created.id.slice(0, 8)} ingested. Queued for classification.`);
    } catch (error) {
      addToast('error', `Failed to ingest ticket: ${errorMessage(error)}`);
    }
  };

  const pendingReviewCount = tickets.filter((t) => t.status === 'draft_for_review').length;
  const autoResolvedCount = tickets.filter((t) => t.status === 'auto_resolved').length;
  const escalatedCount = tickets.filter((t) => t.status === 'escalated').length;
  const handledCount = tickets.filter((t) => t.status === 'auto_resolved' || t.status === 'resolved').length;
  const deflectionRate = tickets.length > 0 ? `${Math.round((handledCount / tickets.length) * 100)}%` : '—';

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}
    >
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenNewTicket={() => setIsModalOpen(true)}
        isBackendConnected={isBackendConnected}
        onRefresh={loadData}
      />

      <div style={{ backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--border-hairline)' }}>
        <div className="app-gutter flex flex-wrap items-center gap-x-6 gap-y-1 py-2 text-[12px]">
          <Stat label="Queue" value={tickets.length} />
          <Stat label="Needs review" value={pendingReviewCount} />
          <Stat label="Auto-resolved" value={autoResolvedCount} />
          <Stat label="Escalated" value={escalatedCount} />
          <span className="ml-auto">
            <Stat label="Deflection" value={deflectionRate} />
          </span>
        </div>
      </div>

      {loadError && (
        <div
          className="app-gutter flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-[12px]"
          style={{
            backgroundColor: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border-hairline)',
            borderLeft: '3px solid var(--status-low)',
          }}
        >
          <span style={{ color: 'var(--text-primary)' }}>Backend unavailable</span>
          <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
            {loadError}
          </span>
          <button
            onClick={loadData}
            className="ml-auto px-3 h-6 text-[12px] font-medium"
            style={{
              color: 'var(--text-primary)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--radius)',
            }}
          >
            Retry
          </button>
        </div>
      )}

      <main className="app-gutter flex-1 min-h-0 py-4">
        {loading && tickets.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div
                className="w-7 h-7 rounded-full border-2 animate-spin"
                style={{ borderColor: 'var(--border-hairline)', borderTopColor: 'var(--text-primary)' }}
              />
              <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
                Loading queue
              </span>
            </div>
          </div>
        ) : activeTab === 'queue' ? (
          <div className="queue-layout">
            <TicketList
              tickets={tickets}
              selectedTicketId={selectedTicket?.id}
              onSelectTicket={handleSelectTicket}
              filterChannel={filterChannel}
              onFilterChannelChange={setFilterChannel}
            />

            {selectedTicket ? (
              <TicketDetailPane
                key={selectedTicket.id}
                ticket={selectedTicket}
                isLoading={detailLoading}
                detailError={detailError}
                onRetryDetail={() => refreshDetail(selectedTicket.id)}
                onApprove={handleApprove}
                onEdit={handleEdit}
                onReject={handleReject}
                onRefund={handleRefund}
                onOrderStatus={handleOrderStatus}
                onPasswordReset={handlePasswordReset}
                onSendMessage={handleSendMessage}
                onClose={handleCloseDetail}
              />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center px-6">
                <span style={{ color: 'var(--text-secondary)' }}>
                  <Icon name="inbox" size={22} />
                </span>
                <p className="text-[13px] font-medium mt-3" style={{ color: 'var(--text-primary)' }}>
                  No ticket selected
                </p>
                <p className="text-[12px] mt-1 max-w-xs" style={{ color: 'var(--text-secondary)' }}>
                  Pick a ticket to see its decision trace, retrieved sources, and draft reply.
                </p>
              </div>
            )}
          </div>
        ) : (
          <AnalyticsDashboardView />
        )}
      </main>

      {isModalOpen && (
        <TicketForm
          onSubmit={handleCreateTicket}
          onCancel={() => setIsModalOpen(false)}
          isOpenAsModal={true}
        />
      )}

      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};
