const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface Ticket {
  id: string;
  customer_id: string;
  subject: string;
  body: string;
  status: string;
  intent: string | null;
  urgency: string | null;
  sentiment: string | null;
  confidence: string | null;
  created_at: string;
  updated_at: string;
  messages?: TicketMessage[];
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  role: string;
  content: string;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface TicketCreate {
  customer_id: string;
  subject: string;
  body: string;
}

export async function createTicket(data: TicketCreate): Promise<Ticket> {
  const response = await fetch(`${API_BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create ticket');
  }
  return response.json();
}

export async function listTickets(): Promise<Ticket[]> {
  const response = await fetch(`${API_BASE}/tickets`);
  if (!response.ok) {
    throw new Error('Failed to fetch tickets');
  }
  return response.json();
}

export async function getTicket(id: string): Promise<Ticket> {
  const response = await fetch(`${API_BASE}/tickets/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch ticket');
  }
  return response.json();
}