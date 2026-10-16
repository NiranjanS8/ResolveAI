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
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const loadTicketDetail = useCallback(async (ticket: Ticket) => {
    try {
      // The list endpoint omits messages/audit logs, so fetch the full record
      // whenever we (re)select a ticket.
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
      if (data.length > 0 && !selectedTicket) {
        await loadTicketDetail(data[0]);
      } else if (selectedTicket) {
        const updated = data.find((t) => t.id === selectedTicket.id);
        if (updated) await loadTicketDetail(updated);
      }
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

  // Handle Approve
  const handleApprove = async (ticket: Ticket) => {
    try {
      const updated = await approveDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Ticket #${ticket.id} approved. AI draft dispatched to customer.`);
    } catch {
      addToast('error', `Failed to approve ticket #${ticket.id}`);
    }
  };

  // Handle Edit Draft
  const handleEdit = async (ticket: Ticket, editedDraft: string) => {
    try {
      const updated = await editDraft(ticket.id, editedDraft);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Edited response for #${ticket.id} sent successfully.`);
    } catch {
      addToast('error', `Failed to edit and send draft for #${ticket.id}`);
    }
  };

  // Handle Reject
  const handleReject = async (ticket: Ticket) => {
    try {
      const updated = await rejectDraft(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('warning', `Ticket #${ticket.id} draft rejected — routed to human escalation.`);
    } catch {
      addToast('error', `Failed to reject ticket #${ticket.id}`);
    }
  };

  // Handle Refund Tool
  const handleRefund = async (ticket: Ticket, amount: number) => {
    try {
      const updated = await processRefundAction(ticket.id, amount);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      if (amount > 2000) {
        addToast('warning', `Refund of ₹${amount} exceeds ₹2,000 threshold. Supervisor approval required.`);
      } else {
        addToast('success', `Refund of ₹${amount} successfully processed under ₹2,000 auto-cap.`);
      }
    } catch {
      addToast('error', `Refund execution failed for #${ticket.id}`);
    }
  };

  // Handle Order Status Tool
  const handleOrderStatus = async (ticket: Ticket) => {
    try {
      const updated = await processOrderStatusAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('info', `Order status lookup executed for #${ticket.id}. Details added to conversation.`);
    } catch {
      addToast('error', `Order status lookup failed`);
    }
  };

  // Handle Password Reset Tool
  const handlePasswordReset = async (ticket: Ticket) => {
    try {
      const updated = await processPasswordResetAction(ticket.id);
      setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('success', `Allow-listed action: Secure password reset link dispatched to ${ticket.customer_id}`);
    } catch {
      addToast('error', `Password reset failed`);
    }
  };

  // Handle Message Send
  const handleSendMessage = async (ticket: Ticket, text: string) => {
    try {
      const newMsg = await addMessage(ticket.id, text, 'agent');
      const updated: Ticket = {
        ...ticket,
        messages: [...(ticket.messages || []), newMsg],
      };
      setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
      await loadTicketDetail(updated);
      addToast('info', `Message posted to conversation.`);
    } catch {
      addToast('error', `Failed to send reply`);
    }
  };

  // Handle Ticket Ingestion
  const handleCreateTicket = async (formData: TicketCreate) => {
    try {
      const created = await createTicket(formData);
      setTickets((prev) => [created, ...prev]);
      await loadTicketDetail(created);
      setIsModalOpen(false);
      addToast('success', `Ticket #${created.id} ingested. LangGraph classified intent: "${created.intent}".`);
    } catch {
      addToast('error', 'Failed to ingest ticket');
    }
  };

  // Quick Stats
  const pendingReviewCount = tickets.filter((t) => t.status === 'draft_for_review').length;
  const autoResolvedCount = tickets.filter((t) => t.status === 'auto_resolved').length;
  const escalatedCount = tickets.filter((t) => t.status === 'escalated').length;
  const deflectionRate = tickets.length > 0 ? Math.round(((autoResolvedCount + tickets.filter(t => t.status === 'resolved').length) / tickets.length) * 100) : 74;

  return (
    <div
      className="flex flex-col"
      style={{ minHeight: '100vh', backgroundColor: 'var(--bg-base)', color: 'var(--text-primary)' }}
    >
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenNewTicket={() => setIsModalOpen(true)}
        isBackendConnected={isBackendConnected}
        onRefresh={loadData}
        ticketCount={tickets.length}
        pendingReviewCount={pendingReviewCount}
      />

      {/* Stats sub-bar — compact, single line */}
      <div
        className="px-5 py-1.5 flex items-center gap-6 text-xs font-mono"
        style={{ backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
      >
        <span style={{ color: 'var(--text-muted)' }}>
          Queue <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{tickets.length}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Review <span style={{ color: 'var(--yellow)', fontWeight: 600 }}>{pendingReviewCount}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Auto-resolved <span style={{ color: 'var(--green)', fontWeight: 600 }}>{autoResolvedCount}</span>
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          Escalated <span style={{ color: 'var(--red)', fontWeight: 600 }}>{escalatedCount}</span>
        </span>
        <span className="ml-auto" style={{ color: 'var(--text-muted)' }}>
          Deflection <span style={{ color: 'var(--green)', fontWeight: 600 }}>{deflectionRate}%</span>
        </span>
      </div>

      {/* Main workspace */}
      <main
        className="flex-1 w-full mx-auto px-5 py-4"
        style={{ maxWidth: '1600px' }}
      >
        {loading && tickets.length === 0 ? (
          <div className="h-[70vh] flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div
                className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
                style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }}
              />
              <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Connecting to broker…
              </span>
            </div>
          </div>
        ) : activeTab === 'queue' ? (
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: '340px 1fr',
              height: 'calc(100vh - 120px)',
            }}
          >
            {/* Left: Queue pane */}
            <div className="overflow-hidden flex flex-col">
              <TicketList
                tickets={tickets}
                selectedTicketId={selectedTicket?.id}
                onSelectTicket={loadTicketDetail}
                filterChannel={filterChannel}
                onFilterChannelChange={setFilterChannel}
              />
            </div>

            {/* Right: Detail pane */}
            <div className="overflow-hidden flex flex-col">
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
                <div
                  className="flex-1 flex flex-col items-center justify-center rounded-lg text-center"
                  style={{
                    border: '1px dashed var(--border)',
                    backgroundColor: 'var(--bg-surface)',
                    color: 'var(--text-muted)',
                  }}
                >
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 text-2xl"
                    style={{ backgroundColor: 'var(--bg-elevated)' }}
                  >
                    📋
                  </div>
                  <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    No ticket selected
                  </p>
                  <p className="text-xs max-w-xs">
                    Select a ticket from the queue to view AI analysis, conversation history, and draft responses.
                  </p>
                </div>
              )}
            </div>
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