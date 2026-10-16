import React, { useState, useEffect } from 'react';
import { getAnalytics, type AnalyticsData } from '../api/tickets';
import { AnalyticsChart } from './AnalyticsChart';

const RANGES: Array<{ id: '24h' | '7d' | '30d'; label: string }> = [
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

export const AnalyticsDashboardView: React.FC = () => {
  const [range, setRange] = useState<'24h' | '7d' | '30d'>('30d');
  const [snapshot, setSnapshot] = useState<{ range: '24h' | '7d' | '30d'; data: AnalyticsData } | null>(null);

  // Loading is derived from whether the fetched snapshot matches the selected
  // range, so the effect never needs to set state synchronously.
  const loading = snapshot?.range !== range;
  const data = snapshot?.range === range ? snapshot.data : null;

  useEffect(() => {
    let mounted = true;
    getAnalytics(range).then((result) => {
      if (mounted) setSnapshot({ range, data: result });
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
            Autonomous deflection, handle time, and cost per ticket.
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
            : data?.executive_summary || 'No summary available for this window yet.'}
        </p>
      </section>

      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 lg:gap-x-6"
        style={{ borderTop: '1px solid var(--border-hairline)', borderBottom: '1px solid var(--border-hairline)' }}
      >
        <Kpi
          label="Autonomous deflection"
          value={data ? `${data.deflection_rate.deflection_rate}%` : '—'}
          note={`${data?.deflection_rate.auto_resolved ?? 0} tickets resolved without an agent`}
        />
        <Kpi
          label="Average handle time"
          value={data ? `${data.average_handle_time.average_handle_time_seconds}s` : '—'}
          note="Human baseline: 14.5 minutes"
        />
        <Kpi
          label="Cost per ticket"
          value={data ? `₹${data.cost_per_ticket.cost_per_ticket.toFixed(2)}` : '—'}
          note="Token inference plus embedding compute"
        />
        <Kpi
          label="CSAT proxy"
          value={data ? `${data.csat_proxy.csat_score.toFixed(1)}%` : '—'}
          note="From customer resolution ratings"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AnalyticsChart title="Deflection rate" metric="deflection_rate" range={range} />
        <AnalyticsChart
          title="Escalation reasons"
          metric="escalation_breakdown"
          range={range}
          data={data?.escalation_breakdown}
        />
        <AnalyticsChart title="Unit economics" metric="cost_per_ticket" range={range} />

        <section
          className="p-4"
          style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-hairline)', borderRadius: 'var(--radius)' }}
        >
          <h3 className="text-[13px] font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Policy and guardrail enforcement
          </h3>
          <GuardrailRow label="Refund cap interceptions" value="14" />
          <GuardrailRow label="Allow-listed tool dispatches" value="100%" />
          <GuardrailRow label="Intent classification accuracy" value="96.8%" />
        </section>
      </div>
    </div>
  );
};
