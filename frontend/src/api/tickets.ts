// ResolveAI Frontend API Client
// Talks to the live FastAPI backend. A failed call fails: nothing is invented.

export type Channel = 'email' | 'chat';
export type TicketStatusType = 'new' | 'draft_for_review' | 'auto_resolved' | 'escalated' | 'resolved';

export interface TicketMessage {
  id: string;
  ticket_id: string;
  role: 'customer' | 'agent' | 'system' | 'ai';
  content: string;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  ticket_id: string;
  action: string;
  payload?: Record<string, unknown> | null;
  confidence?: number | null;
  executed_by: string;
  created_at: string;
}

export interface RetrievedChunk {
  id?: string;
  content?: string;
  source_id?: string;
  source_type?: string;
  doc_title?: string;
  score?: number;
}

export interface Ticket {
  id: string;
  customer_id: string;
  subject: string;
  body: string;
  channel: Channel;
  status: TicketStatusType;
  intent: string | null;
  urgency: 'low' | 'medium' | 'high' | 'critical' | null;
  sentiment: 'positive' | 'neutral' | 'negative' | null;
  confidence: number | null;
  draft_response?: string | null;
  retrieved_context?: RetrievedChunk[] | null;
  created_at: string;
  updated_at: string;
  messages?: TicketMessage[];
  audit_logs?: AuditLogItem[];
}

export interface TicketCreate {
  customer_id: string;
  subject: string;
  body: string;
  channel: Channel;
}

export type AnalyticsRange = '24h' | '7d' | '30d';

/** Mirrors the snapshot served by `app/api/analytics.py`. Every number is
 *  computed from stored rows; a metric the data cannot support is `null`. */
export interface AnalyticsData {
  window: { range: string; since: string; until: string };
  summary: string;
  volume: {
    total: number;
    auto_resolved: number;
    resolved: number;
    draft_for_review: number;
    escalated: number;
    new: number;
    deflected: number;
    deflection_rate: number | null;
  };
  time_to_reply: {
    sample_size: number;
    average_seconds: number | null;
    median_seconds: number | null;
    p95_seconds: number | null;
  };
  cost: {
    currency: string;
    total_cost: number;
    cost_per_ticket: number | null;
    priced_calls: number;
    unpriced_calls: number;
  };
  provider_health: {
    calls: number;
    failures: number;
    error_rate: number | null;
    average_latency_ms: number | null;
    median_latency_ms: number | null;
    p95_latency_ms: number | null;
    by_task: Array<{
      task: string;
      calls: number;
      failures: number;
      cost: number;
      average_latency_ms: number | null;
    }>;
  };
  draft_review: {
    total_reviewed: number;
    approved_unchanged: number;
    edited: number;
    rejected: number;
    acceptance_rate: number | null;
  };
  escalation_reasons: { total_escalated: number; reasons: Record<string, number> };
  guardrails: {
    refund_cap_interceptions: number;
    allow_listed_dispatches: number;
    format_deviations: number;
  };
  deflection_trend: Array<{
    label: string;
    total: number;
    deflected: number;
    deflection_rate: number | null;
  }>;
}

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

/** A failed request carries the server's status and message so the UI can show
 *  what actually went wrong instead of a generic failure. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 8000, ...init } = options;
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) {
    throw new ApiError(await describeError(res), res.status);
  }
  return (await res.json()) as T;
}

async function describeError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg;
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  return `${res.status} ${res.statusText || 'request failed'}`;
}

const jsonPost = (body: unknown): RequestOptions => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const listTickets = () => request<Ticket[]>('/tickets');

export const getTicket = (id: string) => request<Ticket>(`/tickets/${id}`);

/** Ticket creation runs the classification and drafting graph synchronously, so
 *  it needs a window well beyond a normal request. */
export const createTicket = (data: TicketCreate) =>
  request<Ticket>('/tickets', { ...jsonPost(data), timeoutMs: 45000 });

export const approveDraft = (ticketId: string) =>
  request<Ticket>(`/tickets/${ticketId}/approve`, { method: 'POST', timeoutMs: 30000 });

export const editDraft = (ticketId: string, editedDraft: string) =>
  request<Ticket>(`/tickets/${ticketId}/edit`, {
    ...jsonPost({ edited_draft: editedDraft }),
    timeoutMs: 30000,
  });

export const rejectDraft = (ticketId: string) =>
  request<Ticket>(`/tickets/${ticketId}/reject`, { method: 'POST', timeoutMs: 30000 });

export const processRefundAction = (ticketId: string, amount: number) =>
  request<Ticket>(`/tickets/${ticketId}/refund`, { ...jsonPost({ amount }), timeoutMs: 15000 });

export const processOrderStatusAction = (ticketId: string) =>
  request<Ticket>(`/tickets/${ticketId}/order-status`, { method: 'POST', timeoutMs: 15000 });

export const processPasswordResetAction = (ticketId: string) =>
  request<Ticket>(`/tickets/${ticketId}/password-reset`, { method: 'POST', timeoutMs: 15000 });

export const addMessage = (
  ticketId: string,
  content: string,
  role: 'agent' | 'customer' = 'agent',
) => request<TicketMessage>(`/tickets/${ticketId}/messages`, { ...jsonPost({ role, content }), timeoutMs: 10000 });

export const getAnalytics = (range: AnalyticsRange = '30d') =>
  request<AnalyticsData>(`/analytics?range=${range}`, { timeoutMs: 10000 });

/** Human-readable message for anything thrown by the client. */
export const errorMessage = (error: unknown): string => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException && error.name === 'TimeoutError') {
    return 'The backend did not respond in time.';
  }
  return 'Could not reach the backend.';
};
