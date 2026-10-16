import React from 'react';
import type { AnalyticsData, AnalyticsRange } from '../api/tickets';

interface AnalyticsChartProps {
  title: string;
  metric: 'deflection_trend' | 'escalation_breakdown' | 'unit_economics';
  range: AnalyticsRange;
  data: AnalyticsData | null;
}

/* Bars carry no status colour: the confidence tones are reserved for ticket
   confidence tiers, so charts stay neutral and readable. */
const BAR_TRACK = 'var(--border-hairline)';
const BAR_FILL = 'var(--text-secondary)';

const Panel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    className="p-4 space-y-3"
    style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-hairline)' }}
  >
    {children}
  </div>
);

const PanelHeader: React.FC<{ title: string; meta?: string }> = ({ title, meta }) => (
  <div className="flex items-baseline justify-between gap-3">
    <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
      {title}
    </h3>
    {meta && (
      <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
        {meta}
      </span>
    )}
  </div>
);

const Empty: React.FC<{ message: string }> = ({ message }) => (
  <p className="text-[12px] py-2" style={{ color: 'var(--text-secondary)' }}>
    {message}
  </p>
);

const usd = (value: number | null) => (value === null ? '—' : value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`);
const percent = (value: number | null) => (value === null ? '—' : `${value.toFixed(1)}%`);
const millis = (value: number | null) => (value === null ? '—' : `${Math.round(value)}ms`);

const Metric: React.FC<{ label: string; value: string; note: string }> = ({ label, value, note }) => (
  <div>
    <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
      {label}
    </span>
    <span className="text-[18px] font-mono" style={{ color: 'var(--text-primary)' }}>
      {value}
    </span>
    <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
      {note}
    </span>
  </div>
);

export const AnalyticsChart: React.FC<AnalyticsChartProps> = ({ title, metric, range, data }) => {
  if (metric === 'deflection_trend') {
    const trend = data?.deflection_trend ?? [];
    const maxTotal = Math.max(...trend.map((bucket) => bucket.total), 1);
    const labelStep = Math.max(1, Math.ceil(trend.length / 8));

    return (
      <Panel>
        <PanelHeader
          title={title}
          meta={data ? `${percent(data.volume.deflection_rate)} deflected` : undefined}
        />
        {trend.length === 0 ? (
          <Empty message="No tickets in this window." />
        ) : (
          <>
            <div className="h-28 flex items-end gap-[3px]" style={{ borderBottom: `1px solid ${BAR_TRACK}` }}>
              {trend.map((bucket, index) => {
                const height = bucket.total === 0 ? '2px' : `${Math.max(6, (bucket.total / maxTotal) * 100)}%`;
                const deflectedShare = bucket.total > 0 ? (bucket.deflected / bucket.total) * 100 : 0;
                return (
                  <div
                    key={`${bucket.label}-${index}`}
                    className="flex-1 flex flex-col justify-end h-full"
                    title={`${bucket.label}: ${bucket.total} tickets, ${bucket.deflected} deflected`}
                  >
                    <div className="w-full relative" style={{ height, backgroundColor: BAR_TRACK }}>
                      <div
                        className="absolute bottom-0 w-full"
                        style={{ height: `${deflectedShare}%`, backgroundColor: BAR_FILL }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              {trend.map((bucket, index) => (
                <span key={`${bucket.label}-label-${index}`} className="flex-1 text-center truncate">
                  {index % labelStep === 0 ? bucket.label : ''}
                </span>
              ))}
            </div>
          </>
        )}
      </Panel>
    );
  }

  if (metric === 'escalation_breakdown') {
    const reasons = data?.escalation_reasons.reasons ?? {};
    const entries = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
    const total = data?.escalation_reasons.total_escalated ?? 0;
    const maxCount = Math.max(...entries.map(([, count]) => count), 1);

    return (
      <Panel>
        <PanelHeader title={title} meta={`${total} escalated`} />
        {entries.length === 0 ? (
          <Empty message="No escalations in this window." />
        ) : (
          <div className="space-y-2.5 pt-1">
            {entries.map(([label, count]) => {
              const pct = Math.round((count / maxCount) * 100);
              return (
                <div key={label} className="space-y-1">
                  <div className="flex justify-between gap-3 text-[12px]">
                    <span className="truncate" style={{ color: 'var(--text-secondary)' }}>
                      {label}
                    </span>
                    <span className="font-mono shrink-0" style={{ color: 'var(--text-primary)' }}>
                      {count}
                    </span>
                  </div>
                  <div className="w-full h-1.5 overflow-hidden" style={{ backgroundColor: BAR_TRACK }}>
                    <div
                      className="h-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: BAR_FILL }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader title={title} meta={range} />
      {!data ? (
        <Empty message="No provider activity in this window." />
      ) : (
        <div className="grid grid-cols-2 gap-4 pt-2">
          <Metric
            label="Provider spend"
            value={usd(data.cost.total_cost)}
            note={`${data.cost.priced_calls} priced calls`}
          />
          <Metric
            label="Cost per ticket"
            value={usd(data.cost.cost_per_ticket)}
            note={data.cost.unpriced_calls > 0 ? `${data.cost.unpriced_calls} calls unpriced` : 'All calls priced'}
          />
          <Metric
            label="Latency median"
            value={millis(data.provider_health.median_latency_ms)}
            note={`p95 ${millis(data.provider_health.p95_latency_ms)}`}
          />
          <Metric
            label="Provider errors"
            value={percent(data.provider_health.error_rate)}
            note={`${data.provider_health.failures} of ${data.provider_health.calls} calls`}
          />
        </div>
      )}
    </Panel>
  );
};
