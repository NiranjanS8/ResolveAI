import React, { useState, useEffect, useCallback } from 'react';
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
  checkBackendHealth,
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
  const [filterChannel, setFilterChannel] = useState<'all' | Channel>('all');
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

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

  const loadTicketDetail = useCallback(async (ticket: Ticket) => {
    try {
      // The list endpoint omits messages/audit logs, so fetch the full record
      // whenever a ticket is selected.
      const detail = await getTicket(ticket.id);
      setSelectedTicket(detail);
    } catch {
      setSelectedTicket(ticket);
    }
  }, []);

  const loadData = useCallback(async () => {
    try {
      const isOnline = await checkBackendHealth();
      setIsBackendConnected(isOnline);
      const data = await listTickets();
      setTickets(data);
      // Fall back to the newest ticket when the selected one is gone (deleted, or
      // filtered out between polls) so the detail pane never strands a stale id.
      const target = data.find((t) => t.id === selectedTicket?.id) ?? data[0];
      if (target) await loadTicketDetail(target);
      else setSelectedTicket(null);
    } catch {
      setIsBackendConnected(false);
    } finally {
      setLoading(false);
    }
  }, [selectedTicket, loadTicketDetail]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleApprove = async (ticket: Ticket) => {
    try {
      const updated = await approveDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Ticket #${ticket.id.slice(0, 8)} approved. AI draft dispatched to customer.`);
    } catch {
      addToast('error', `Failed to approve ticket #${ticket.id.slice(0, 8)}`);
    }
  };

  const handleEdit = async (ticket: Ticket, editedDraft: string) => {
    try {
      const updated = await editDraft(ticket.id, editedDraft);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Edited response for #${ticket.id.slice(0, 8)} sent successfully.`);
    } catch {
      addToast('error', `Failed to edit and send draft for #${ticket.id.slice(0, 8)}`);
    }
  };

  const handleReject = async (ticket: Ticket) => {
    try {
      const updated = await rejectDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('warning', `Ticket #${ticket.id.slice(0, 8)} draft rejected. Routed to a human.`);
    } catch {
      addToast('error', `Failed to reject ticket #${ticket.id.slice(0, 8)}`);
    }
  };

  const handleRefund = async (ticket: Ticket, amount: number) => {
    try {
      const updated = await processRefundAction(ticket.id, amount);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      if (amount > 2000) {
        addToast('warning', `Refund of ₹${amount} exceeds the ₹2,000 cap. Supervisor approval required.`);
      } else {
        addToast('success', `Refund of ₹${amount} processed under the ₹2,000 auto-cap.`);
      }
    } catch {
      addToast('error', `Refund execution failed for #${ticket.id.slice(0, 8)}`);
    }
  };

  const handleOrderStatus = async (ticket: Ticket) => {
    try {
      const updated = await processOrderStatusAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('info', `Order status lookup executed for #${ticket.id.slice(0, 8)}.`);
    } catch {
      addToast('error', 'Order status lookup failed');
    }
  };

  const handlePasswordReset = async (ticket: Ticket) => {
    try {
      const updated = await processPasswordResetAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Secure password reset link dispatched to ${ticket.customer_id}`);
    } catch {
      addToast('error', 'Password reset failed');
    }
  };

  const handleSendMessage = async (ticket: Ticket, text: string) => {
    try {
      const newMessage = await addMessage(ticket.id, text, 'agent');
      const updated: Ticket = { ...ticket, messages: [...(ticket.messages || []), newMessage] };
      setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('info', 'Message posted to the conversation.');
    } catch {
      addToast('error', 'Failed to send reply');
    }
  };

  const handleCreateTicket = async (formData: TicketCreate) => {
    try {
      const created = await createTicket(formData);
      setTickets((prev) => [created, ...prev]);
      await loadTicketDetail(created);
      setIsModalOpen(false);
      addToast('success', `Ticket #${created.id.slice(0, 8)} ingested. Classified as "${created.intent}".`);
    } catch {
      addToast('error', 'Failed to ingest ticket');
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
              onSelectTicket={loadTicketDetail}
              filterChannel={filterChannel}
              onFilterChannelChange={setFilterChannel}
            />

            {selectedTicket ? (
              <TicketDetailPane
                ticket={selectedTicket}
                onApprove={handleApprove}
                onEdit={handleEdit}
                onReject={handleReject}
                onRefund={handleRefund}
                onOrderStatus={handleOrderStatus}
                onPasswordReset={handlePasswordReset}
                onSendMessage={handleSendMessage}
                onClose={() => setSelectedTicket(null)}
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
