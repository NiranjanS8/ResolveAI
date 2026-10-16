import type { Channel, Ticket } from '../api/tickets';

/**
 * The single rendering contract for a ticket.
 *
 * The queue list and the detail pane both read from here so a ticket can never
 * show one confidence in the list and another in the detail, or one channel in
 * one place and a different one in the other. Confidence is always shown as the
 * model's raw certainty (one field, one number); the weighted decision score is
 * derived in the Decision trace from the same formula the backend uses.
 */

/* Mirrors backend/app/core/thresholds.py — the numbers that actually drive
   routing. Keeping them here means the UI colours confidence tiers with the
   same cut-offs that produced the status, instead of ad-hoc 90/75 guesses. */
const DECISION_THRESHOLDS: Record<string, { high: number; medium: number }> = {
  refund: { high: 0.7, medium: 0.5 },
  technical: { high: 0.8, medium: 0.6 },
  billing: { high: 0.75, medium: 0.55 },
  account: { high: 0.7, medium: 0.5 },
  order_status: { high: 0.65, medium: 0.45 },
  password_reset: { high: 0.65, medium: 0.45 },
  cancellation: { high: 0.7, medium: 0.5 },
  general: { high: 0.6, medium: 0.4 },
};

export const REFUND_INR_CAP = 2000;

export type ConfidenceTier = 'high' | 'medium' | 'low';

export const thresholdsFor = (intent: string | null | undefined) =>
  DECISION_THRESHOLDS[intent ?? 'general'] ?? DECISION_THRESHOLDS.general;

export const tierForScore = (score: number, intent: string | null | undefined): ConfidenceTier => {
  const { high, medium } = thresholdsFor(intent);
  if (score >= high) return 'high';
  if (score >= medium) return 'medium';
  return 'low';
};

/* Status is the confidence tier made visible: auto-resolved is high, needs
   review is medium, escalated is low. `new` has no tier yet. */
const STATUS_TIER: Record<string, ConfidenceTier | null> = {
  auto_resolved: 'high',
  resolved: 'high',
  draft_for_review: 'medium',
  escalated: 'low',
  new: null,
};

const TIER_VAR: Record<ConfidenceTier, string> = {
  high: 'var(--status-high)',
  medium: 'var(--status-medium)',
  low: 'var(--status-low)',
};

const TIER_BG_VAR: Record<ConfidenceTier, string> = {
  high: 'var(--status-high-bg)',
  medium: 'var(--status-medium-bg)',
  low: 'var(--status-low-bg)',
};

export const STATUS_LABEL: Record<string, string> = {
  auto_resolved: 'Auto-resolved',
  draft_for_review: 'Needs review',
  escalated: 'Escalated',
  resolved: 'Resolved',
  new: 'New',
};

export const statusLabel = (status: string) => STATUS_LABEL[status] ?? status;

export const statusTier = (status: string): ConfidenceTier | null => STATUS_TIER[status] ?? null;

export const tierColor = (tier: ConfidenceTier | null) =>
  tier === null ? 'var(--text-secondary)' : TIER_VAR[tier];

export const tierBackground = (tier: ConfidenceTier | null) =>
  tier === null ? 'transparent' : TIER_BG_VAR[tier];

/** Status tone used to colour a row's 3px left border. */
export const statusColor = (status: string) => tierColor(statusTier(status));

const INTENT_LABEL: Record<string, string> = {
  general: 'General',
  billing: 'Billing',
  technical: 'Technical',
  account: 'Account',
  refund: 'Refund',
  order_status: 'Order status',
  password_reset: 'Password reset',
  cancellation: 'Cancellation',
};

export const intentLabel = (intent: string | null | undefined) =>
  intent ? INTENT_LABEL[intent] ?? intent : null;

export const CHANNEL_LABEL: Record<Channel, string> = {
  email: 'Email',
  chat: 'Chat',
};

export const channelLabel = (channel: Channel) => CHANNEL_LABEL[channel] ?? channel;

export const SENTIMENT_LABEL: Record<string, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
};

export const sentimentLabel = (sentiment: string | null | undefined) =>
  SENTIMENT_LABEL[sentiment ?? 'neutral'] ?? 'Neutral';

export const URGENCY_LABEL: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

export const urgencyLabel = (urgency: string | null | undefined) =>
  URGENCY_LABEL[urgency ?? 'medium'] ?? 'Medium';

/* ─── Confidence ───────────────────────────────────────────────────────── */

/** The classifier's own certainty — the one confidence number shown per ticket. */
export const classifierCertainty = (ticket: Pick<Ticket, 'confidence'>): number | null => {
  const value = Number(ticket.confidence);
  return Number.isFinite(value) ? value : null;
};

/** Relevance of the best-matching knowledge chunk (detail payload only). */
export const retrievalRelevance = (
  retrieved: ReadonlyArray<{ score?: number }> | null | undefined,
): number | null => {
  if (!retrieved || retrieved.length === 0) return null;
  const best = Math.max(...retrieved.map((chunk) => Number(chunk?.score ?? 0)));
  return Number.isFinite(best) && best > 0 ? best : null;
};

/** The weighted score the router actually compared against the thresholds. */
export const routingScore = (ticket: Ticket): number | null => {
  const certainty = classifierCertainty(ticket);
  const relevance = retrievalRelevance(ticket.retrieved_context);
  if (certainty === null || relevance === null) return null;
  return certainty * relevance;
};

/* ─── Formatting ───────────────────────────────────────────────────────── */

/** Data is monospace and fixed-precision: `0.94`, never `94%`. */
export const formatScore = (score: number | null) => (score === null ? '—' : score.toFixed(2));

export const shortId = (id: string) => id.slice(0, 8);

export const formatRelativeTime = (isoString: string) => {
  const diffMins = Math.floor((Date.now() - new Date(isoString).getTime()) / 60000);
  if (!Number.isFinite(diffMins)) return '';
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export const formatTimestamp = (isoString: string) =>
  new Date(isoString).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

export const formatClockTime = (isoString: string) =>
  new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/** Short human-readable serial of a ticket id, for copy affordances. */
export const copyToClipboard = async (value: string) => {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
};
