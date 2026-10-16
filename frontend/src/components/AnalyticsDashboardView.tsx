import React, { useState, useEffect } from 'react';
import {
  getAnalytics,
  errorMessage,
  type AnalyticsData,
  type AnalyticsRange,
} from '../api/tickets';
import { AnalyticsChart } from './AnalyticsChart';

const RANGES: Array<{ id: AnalyticsRange; label: string }> = [
  { id: '24h', label: 'Last 24 hours' },
  { id: '7d', label: 'Last 7 days' },
  { id: '30d', label: 'Last 30 days' },
];

const Kpi: React.FC<{ label: string; value: string; note: string }> = ({ label, value, note }) => (
  <div className="py-4 pr-6">
    <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
      {label}
    </span>
    <span className="text-[22px] font-mono" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
    <span className="text-[12px] block mt-1" style={{ color: 'var(--text-secondary)' }}>
      {note}
    </span>
  </div>
);

const GuardrailRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div
    className="flex items-center justify-between gap-4 py-2"
    style={{ borderBottom: '1px solid var(--border-hairline)' }}
  >
    <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
      {label}
    </span>
    <span className="text-[13px] font-mono" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
  </div>
);

type Snapshot = { range: AnalyticsRange; data: AnalyticsData | null; error: string | null };

const percent = (value: number | null) => (value === null ? '—' : `${value.toFixed(1)}%`);
const usd = (value: number | null) => (value === null ? '—' : value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`);
const seconds = (value: number | null) => (value === null ? '—' : `${value.toFixed(1)}s`);

export const AnalyticsDashboardView: React.FC = () => {
  const [range, setRange] = useState<AnalyticsRange>('30d');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);

  // The snapshot is keyed by range, so loading, data and error are all derived
  // from whether the current range has been fetched — no synchronously-set state.
  const current = snapshot?.range === range ? snapshot : null;
  const loading = current === null;
  const data = current?.data ?? null;
  const error = current?.error ?? null;

  useEffect(() => {
    let mounted = true;
    getAnalytics(range)
      .then((result) => {
        if (mounted) setSnapshot({ range, data: result, error: null });
      })
      .catch((err: unknown) => {
        if (mounted) setSnapshot({ range, data: null, error: errorMessage(err) });
      });
    return () => {
      mounted = false;
    };
  }, [range]);

  return (
    <div className="h-full overflow-y-auto space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-baseline justify-between gap-4 pb-3" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
        <div>
          <h2 className="text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>
            Operations and ROI
          </h2>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Measured from stored tickets, messages, provider calls and audit entries.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {RANGES.map((option) => {
            const active = range === option.id;
            return (
              <button
                key={option.id}
                id={`analytics-range-${option.id}`}
                onClick={() => setRange(option.id)}
                className="text-[12px] font-medium"
                style={{
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  borderBottom: `2px solid ${active ? 'var(--text-primary)' : 'transparent'}`,
                  paddingBottom: 2,
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      <section>
        <h3 className="text-[13px] font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          Summary
        </h3>
        <p className="text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          {loading
            ? 'Recalculating metrics.'
            : error
              ? `Could not load analytics: ${error}`
              : data?.summary || 'No data for this window.'}
        </p>
      </section>

      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 lg:gap-x-6"
        style={{ borderTop: '1px solid var(--border-hairline)', borderBottom: '1px solid var(--border-hairline)' }}
      >
        <Kpi
          label="Autonomous deflection"
          value={data ? percent(data.volume.deflection_rate) : '—'}
          note={
            data
              ? `${data.volume.deflected} of ${data.volume.total} tickets resolved without an agent`
              : 'No tickets in this window'
          }
        />
        <Kpi
          label="Time to first reply"
          value={data ? seconds(data.time_to_reply.median_seconds) : '—'}
          note={
            data && data.time_to_reply.sample_size > 0
              ? `Median across ${data.time_to_reply.sample_size} replies`
              : 'No replies recorded yet'
          }
        />
        <Kpi
          label="Cost per ticket"
          value={data ? usd(data.cost.cost_per_ticket) : '—'}
          note={
            data && data.cost.unpriced_calls > 0
              ? `USD · ${data.cost.unpriced_calls} calls unpriced`
              : 'USD, from real token usage'
          }
        />
        <Kpi
          label="Draft acceptance"
          value={data ? percent(data.draft_review.acceptance_rate) : '—'}
          note={
            data && data.draft_review.total_reviewed > 0
              ? `${data.draft_review.approved_unchanged} of ${data.draft_review.total_reviewed} approved unchanged`
              : 'No drafts reviewed yet'
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AnalyticsChart title="Tickets and deflection over time" metric="deflection_trend" range={range} data={data} />
        <AnalyticsChart title="Escalation reasons" metric="escalation_breakdown" range={range} data={data} />
        <AnalyticsChart title="Unit economics and provider health" metric="unit_economics" range={range} data={data} />

        <section
          className="p-4"
          style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-hairline)' }}
        >
          <h3 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Policy and guardrail enforcement
          </h3>
          <GuardrailRow
            label="Refund cap interceptions"
            value={data ? String(data.guardrails.refund_cap_interceptions) : '—'}
          />
          <GuardrailRow
            label="Allow-listed tool dispatches"
            value={data ? String(data.guardrails.allow_listed_dispatches) : '—'}
          />
          <GuardrailRow
            label="Format deviations corrected"
            value={data ? String(data.guardrails.format_deviations) : '—'}
          />
          <GuardrailRow
            label="Provider errors"
            value={data ? `${data.provider_health.failures}` : '—'}
          />
        </section>
      </div>
    </div>
  );
};
